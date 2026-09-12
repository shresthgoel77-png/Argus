import uuid
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func

from app.models.github_event import GitHubEvent
from app.integrations.github.webhook_events import NormalizedWebhookEvent
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

def _strip_secrets(error_str: str) -> str:
    """Removes sensitive webhook secrets from error messages."""
    secret = settings.GITHUB_WEBHOOK_SECRET
    if secret and secret in error_str:
        error_str = error_str.replace(secret, "***STRIPPED_SECRET***")
    return error_str

def record_event(
    db: Session,
    normalized_event: NormalizedWebhookEvent,
    repository_id: uuid.UUID | None
) -> GitHubEvent | None:
    """
    Attempts to insert a new GitHubEvent row.
    Returns None if the delivery_id already exists (caught via IntegrityError).
    """
    event = GitHubEvent(
        delivery_id=normalized_event.delivery_id,
        event_type=normalized_event.event_type,
        action=normalized_event.action,
        installation_id=normalized_event.installation_id,
        repository_github_id=normalized_event.repository.github_repo_id if normalized_event.repository else None,
        repository_id=repository_id,
        payload=normalized_event.raw_payload,
        status="received"
    )
    db.add(event)
    
    try:
        db.commit()
    except IntegrityError:
        # This delivery was already recorded
        db.rollback()
        return None
        
    db.refresh(event)
    return event

def mark_processed(db: Session, event: GitHubEvent) -> GitHubEvent:
    """Marks an event as processed."""
    event.status = "processed"
    event.processed_at = func.now()
    db.commit()
    db.refresh(event)
    return event

def mark_ignored(db: Session, event: GitHubEvent) -> GitHubEvent:
    """Marks an event as ignored."""
    event.status = "ignored"
    event.processed_at = func.now()
    db.commit()
    db.refresh(event)
    return event

def mark_failed(db: Session, event: GitHubEvent, error: Exception) -> GitHubEvent:
    """Marks an event as failed and stores a safe exception message."""
    event.status = "failed"
    error_msg = str(error)
    
    # Strip potential secrets
    error_msg = _strip_secrets(error_msg)
    
    # Truncate to reasonable length (e.g., 1000 chars) to prevent DB bloat
    if len(error_msg) > 1000:
        error_msg = error_msg[:997] + "..."
        
    event.error_message = error_msg
    event.processed_at = func.now()
    db.commit()
    db.refresh(event)
    return event
