import time
import uuid
import random
import asyncio
import json
import os
from collections import OrderedDict
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import Counter, Histogram, generate_latest

from fastapi.middleware.cors import CORSMiddleware
from config import get_config
from logging_setup import logger
from razorpay_utils import build_test_payment_event, sign_payload, verify_signature

app = FastAPI(title="Simulator Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["endpoint", "status"]
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["endpoint"]
)
WEBHOOK_FAILURES_TOTAL = Counter(
    "webhook_failures_total",
    "Total webhook failures"
)
RAZORPAY_WEBHOOK_SIGNATURE_FAILURES_TOTAL = Counter(
    "razorpay_webhook_signature_failures_total",
    "Total Razorpay webhook signature verification failures"
)
RAZORPAY_WEBHOOK_DUPLICATE_EVENTS_TOTAL = Counter(
    "razorpay_webhook_duplicate_events_total",
    "Total duplicate Razorpay webhook events"
)
RAZORPAY_WEBHOOK_PROCESSED_TOTAL = Counter(
    "razorpay_webhook_processed_total",
    "Total Razorpay webhook processing outcomes",
    ["result"]
)

# Demo-scope deduplication state; this resets when the simulator process restarts.
MAX_SEEN_EVENTS = 1000
_seen_razorpay_event_ids = OrderedDict()
_last_demo_event_id: str | None = None

@app.middleware("http")
async def process_metrics_and_log(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as e:
        status_code = 500
        response = JSONResponse(status_code=500, content={"status": "error", "message": "Internal Server Error"})

    end_time = time.time()
    latency_seconds = end_time - start_time
    latency_ms = round(latency_seconds * 1000, 2)
    
    endpoint = request.url.path
    
    # Update metrics
    HTTP_REQUESTS_TOTAL.labels(endpoint=endpoint, status=str(status_code)).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(endpoint=endpoint).observe(latency_seconds)
    
    if endpoint == "/webhook/payment-event" and status_code >= 500:
        WEBHOOK_FAILURES_TOTAL.inc()

    # Logging
    log_data = {
        "request_id": request_id,
        "endpoint": endpoint,
        "method": request.method,
        "status_code": status_code,
        "latency_ms": latency_ms,
    }
    
    if status_code >= 400:
        log_data["error"] = "Error encountered during request processing"

    logger.info(log_data)
    
    return response


@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/api/checkout")
async def checkout():
    cfg = get_config()
    jitter = random.uniform(0, cfg.get("latency_ms_jitter", 20))
    total_sleep_ms = cfg.get("latency_ms_base", 50) + jitter
    await asyncio.sleep(total_sleep_ms / 1000.0)
    
    if random.random() < cfg.get("error_rate", 0.0):
        return JSONResponse(status_code=500, content={"status": "error"})
        
    return {"status": "ok", "latency_ms": total_sleep_ms}

@app.post("/webhook/payment-event")
async def payment_event():
    cfg = get_config()
    jitter = random.uniform(0, cfg.get("latency_ms_jitter", 20))
    total_sleep_ms = cfg.get("latency_ms_base", 50) + jitter
    await asyncio.sleep(total_sleep_ms / 1000.0)
    
    if random.random() < cfg.get("webhook_failure_rate", 0.0):
        return JSONResponse(status_code=500, content={"status": "error"})
        
    return {"status": "received"}


async def _simulate_razorpay_processing():
    cfg = get_config()
    jitter = random.uniform(0, cfg.get("latency_ms_jitter", 20))
    total_sleep_ms = cfg.get("latency_ms_base", 50) + jitter
    await asyncio.sleep(total_sleep_ms / 1000.0)

    if random.random() < cfg.get("webhook_failure_rate", 0.0):
        return 500, {"status": "error"}

    return 200, {"status": "received"}


async def _process_razorpay_webhook(raw_body: bytes, signature_header):
    # This fallback is only a local-dev/demo placeholder, never a real Razorpay secret.
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "test_webhook_secret_change_me")
    if not verify_signature(secret, raw_body, signature_header):
        RAZORPAY_WEBHOOK_SIGNATURE_FAILURES_TOTAL.inc()
        RAZORPAY_WEBHOOK_PROCESSED_TOTAL.labels(result="rejected_signature").inc()
        logger.info({"event": "razorpay_webhook", "signature_valid": False})
        return 400, {"status": "invalid_signature"}

    try:
        body = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
        return 400, {"status": "invalid_payload"}

    event_id = body.get("id") if isinstance(body, dict) else None
    if not isinstance(event_id, str) or not event_id:
        return 400, {"status": "missing_event_id"}

    if event_id in _seen_razorpay_event_ids:
        RAZORPAY_WEBHOOK_DUPLICATE_EVENTS_TOTAL.inc()
        RAZORPAY_WEBHOOK_PROCESSED_TOTAL.labels(result="duplicate").inc()
        logger.info({"event_id": event_id, "duplicate": True})
        return 200, {"status": "duplicate_ignored", "event_id": event_id}

    _seen_razorpay_event_ids[event_id] = None
    if len(_seen_razorpay_event_ids) > MAX_SEEN_EVENTS:
        _seen_razorpay_event_ids.popitem(last=False)

    status_code, result = await _simulate_razorpay_processing()
    RAZORPAY_WEBHOOK_PROCESSED_TOTAL.labels(result="accepted").inc()
    result["event_id"] = event_id
    return status_code, result


@app.post("/webhook/razorpay-event")
async def razorpay_event(request: Request):
    raw_body = await request.body()
    status_code, body = await _process_razorpay_webhook(
        raw_body, request.headers.get("X-Razorpay-Signature")
    )
    return JSONResponse(status_code=status_code, content=body)


@app.post("/simulate/razorpay-webhook")
async def simulate_razorpay_webhook(variant: str):
    global _last_demo_event_id
    if variant not in {"valid", "tampered", "duplicate"}:
        return JSONResponse(status_code=400, content={"status": "unknown_variant"})

    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "test_webhook_secret_change_me")
    event = build_test_payment_event()
    if variant == "duplicate":
        if _last_demo_event_id is None:
            _last_demo_event_id = event["id"]
        event["id"] = _last_demo_event_id
        raw_body = json.dumps(event).encode()
        signature = sign_payload(secret, raw_body)
    else:
        if variant == "valid":
            _last_demo_event_id = event["id"]
        raw_body = json.dumps(event).encode()
        signature = sign_payload(secret, raw_body)
        if variant == "tampered":
            signature = ("1" if signature[0] != "1" else "0") + signature[1:]

    import requests
    backend_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
    webhook_url = f"{backend_url}/webhooks/razorpay"
    try:
        resp = requests.post(webhook_url, data=raw_body, headers={"X-Razorpay-Signature": signature}, timeout=3.0)
        status_code = resp.status_code
        try:
            result = resp.json()
        except BaseException:
            result = {"status": "invalid_response", "body": resp.text}
    except requests.RequestException as e:
        status_code = 502
        result = {"status": "backend_unreachable", "error": str(e)}

    response = {"variant": variant, "result": result, "event_id": event["id"]}
    return JSONResponse(status_code=200, content=response)

@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type="text/plain")

from deploy_sim import trigger_bad_deployment, trigger_reset, get_state, BAD_CONFIG

@app.post("/simulate/bad-deployment")
async def bad_deployment():
    # Only for demo/local environment. DO NOT expose in real production.
    state = get_state()
    if state["bad_deployment_active"]:
        return JSONResponse(status_code=409, content={"status": "already_active"})
        
    sha = trigger_bad_deployment()
    return {"status": "bad_deployment_triggered", "commit_sha": sha, "applied_config": BAD_CONFIG}

@app.post("/simulate/reset")
async def reset_deployment():
    # Only for demo/local environment. DO NOT expose in real production.
    # Note: This is a LOW-LEVEL primitive only. It is intentionally not gated by 
    # approval here — the approval-gated wrapper around this capability is 
    # built in Phase 7 (Safe Remediation). Do not confuse this with governed remediation.
    sha = trigger_reset()
    return {"status": "reset", "commit_sha": sha}

@app.get("/simulate/state")
async def get_simulator_state():
    # Only for demo/local environment. DO NOT expose in real production.
    return get_state()
