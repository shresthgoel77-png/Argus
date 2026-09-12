from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import json

from app.db.session import get_db
from app.integrations.github.webhook_security import verify_signature
from app.integrations.github.webhook_events import parse_webhook_payload
from app.services.github_event_service import process_webhook_event
from app.integrations.github.client import GitHubAppClient

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

@router.post("/github", status_code=status.HTTP_200_OK)
async def github_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Public, unauthenticated endpoint for receiving GitHub webhooks.
    """
    delivery_id = request.headers.get("x-github-delivery")
    event_type = request.headers.get("x-github-event")
    signature = request.headers.get("x-hub-signature-256")
    
    if not delivery_id or not event_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing delivery or event headers."
        )
        
    body = await request.body()
    
    if not verify_signature(body, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized"
        )
        
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON body"
        )
        
    normalized_event = parse_webhook_payload(event_type, delivery_id, payload)
    
    client = None
    if normalized_event.installation_id:
        client = GitHubAppClient(installation_id=normalized_event.installation_id)
        
    process_webhook_event(db, normalized_event, client)
    
    return {"status": "ok"}
