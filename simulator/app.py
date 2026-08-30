import time
import uuid
import random
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import Counter, Histogram, generate_latest

from fastapi.middleware.cors import CORSMiddleware
from .config import get_config
from .logging_setup import logger

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

@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type="text/plain")

from .deploy_sim import trigger_bad_deployment, trigger_reset, get_state, BAD_CONFIG

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
