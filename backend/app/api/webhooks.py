import hashlib
import hmac
import json
import os
import datetime
from collections import OrderedDict
from fastapi import APIRouter, Request, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Incident
from app.github.engine import auto_create_incident_issue

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

MAX_SEEN_EVENTS = 1000
_seen_razorpay_event_ids = OrderedDict()

def sign_payload(secret: str, raw_body: bytes) -> str:
    return hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()

def verify_signature(secret: str, raw_body: bytes, signature_header: str | None) -> bool:
    if signature_header is None:
        return False
    computed = sign_payload(secret, raw_body)
    return hmac.compare_digest(computed, signature_header)

@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    raw_body = await request.body()
    signature_header = request.headers.get("X-Razorpay-Signature")
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "test_webhook_secret_change_me")
    
    if not verify_signature(secret, raw_body, signature_header):
        # Create incident
        incident = Incident(
            type="webhook_failure",
            service="simulator",
            severity="high",
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            trigger="tampered_signature",
            status="open",
            initial_metrics={"firing": True, "value": 1.0, "type": "webhook_failure"}
        )
        db.add(incident)
        db.commit()
        db.refresh(incident)
        
        background_tasks.add_task(auto_create_incident_issue, incident.id)
        return JSONResponse(status_code=400, content={"status": "invalid_signature"})

    try:
        body = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
        return JSONResponse(status_code=400, content={"status": "invalid_payload"})

    event_id = body.get("id") if isinstance(body, dict) else None
    if not isinstance(event_id, str) or not event_id:
        return JSONResponse(status_code=400, content={"status": "missing_event_id"})

    if event_id in _seen_razorpay_event_ids:
        # Create incident
        incident = Incident(
            type="webhook_failure",
            service="simulator",
            severity="high",
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            trigger="duplicate_event",
            status="open",
            initial_metrics={"firing": True, "value": 1.0, "type": "webhook_failure"}
        )
        db.add(incident)
        db.commit()
        db.refresh(incident)
        
        background_tasks.add_task(auto_create_incident_issue, incident.id)
        return JSONResponse(status_code=200, content={"status": "duplicate_ignored", "event_id": event_id})

    _seen_razorpay_event_ids[event_id] = None
    if len(_seen_razorpay_event_ids) > MAX_SEEN_EVENTS:
        _seen_razorpay_event_ids.popitem(last=False)

    return JSONResponse(status_code=200, content={"status": "received", "event_id": event_id})
