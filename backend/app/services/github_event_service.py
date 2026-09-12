import uuid
from typing import Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func

from app.models.github_event import GitHubEvent
from app.models.github_connection import GitHubConnection
from app.models.repository import Repository
from app.integrations.github.webhook_events import NormalizedWebhookEvent
from app.services.github_connection_service import handle_installation_status_change
from app.services.repository_service import disable_monitoring_for_removed_repositories
from app.core.config import settings
from app.core.logging import get_logger
from app.monitoring import monitor_service as MonitorService

logger = get_logger(__name__)

EVENT_TYPE_TO_ANALYZER: dict[str, str] = {
    "workflow_run": "ci",
    "pull_request": "pull_request",
    "issues": "issue",
    "push": "repository_activity",
}

def _run_analyzer_sync(coro_func, *args, **kwargs):
    import asyncio
    import threading
    result = None
    exc = None
    def _run():
        nonlocal result, exc
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(coro_func(*args, **kwargs))
        except Exception as e:
            exc = e
        finally:
            loop.close()
            
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None
        
    if current_loop:
        t = threading.Thread(target=_run)
        t.start()
        t.join()
        if exc:
            raise exc
        return result
    else:
        return asyncio.run(coro_func(*args, **kwargs))


def _strip_secrets(error_str: str) -> str:
    """Removes sensitive webhook secrets from error messages."""
    secret = settings.github_app_webhook_secret.get_secret_value() if settings.github_app_webhook_secret else None
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
    try:
        with db.begin_nested():
            db.add(event)
        db.commit()
    except IntegrityError:
        # This delivery was already recorded
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

def process_webhook_event(
    db: Session, normalized_event: NormalizedWebhookEvent, client: Any
) -> GitHubEvent | None:
    """
    Main orchestration entry point for processing GitHub webhooks.
    Records the event, attempts any configured reactions, and marks the
    event status based on success/failure and reaction applicability.
    """
    repository_id = None
    if normalized_event.repository:
        repo = (
            db.query(Repository)
            .filter(
                Repository.github_repo_id == normalized_event.repository.github_repo_id,
                Repository.monitoring_enabled == True,
            )
            .first()
        )
        if repo:
            repository_id = repo.id
            
    event = record_event(db, normalized_event, repository_id)
    if not event:
        return None
        
    is_reaction_event = False
    if normalized_event.event_type == "installation" and normalized_event.action in {
        "deleted", "suspend", "unsuspend", "new_permissions_accepted"
    }:
        is_reaction_event = True
    elif normalized_event.event_type == "installation_repositories":
        is_reaction_event = True
    elif repository_id is not None and normalized_event.event_type in EVENT_TYPE_TO_ANALYZER:
        is_reaction_event = True
        
    try:
        if (
            normalized_event.event_type == "installation"
            and normalized_event.action in {"deleted", "suspend", "unsuspend", "new_permissions_accepted"}
        ):
            if normalized_event.installation_id is not None:
                handle_installation_status_change(
                    db, normalized_event.installation_id, normalized_event.action
                )
                
        elif (
            normalized_event.event_type == "installation_repositories"
            and normalized_event.installation_id is not None
        ):
            conn = (
                db.query(GitHubConnection)
                .filter(GitHubConnection.installation_id == normalized_event.installation_id)
                .first()
            )
            if conn and normalized_event.repositories_removed:
                disable_monitoring_for_removed_repositories(
                    db, conn, normalized_event.repositories_removed
                )
                
        elif repository_id is not None and normalized_event.event_type in EVENT_TYPE_TO_ANALYZER:
            analyzer_key = EVENT_TYPE_TO_ANALYZER[normalized_event.event_type]
            _run_analyzer_sync(
                MonitorService.run_analyzer,
                db=db,
                analyzer_key=analyzer_key,
                repository=repo,
                normalized_event=normalized_event
            )
                
    except Exception as e:
        return mark_failed(db, event, e)
        
    if is_reaction_event:
        return mark_processed(db, event)
    else:
        return mark_ignored(db, event)
