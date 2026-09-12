import uuid
import pytest
import concurrent.futures
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Any

from app.models.repository import Repository
from app.models.user import User
from app.models.github_event import GitHubEvent
from app.integrations.github.webhook_events import NormalizedWebhookEvent, RepoRef
from app.services.github_event_service import record_event, mark_processed, mark_ignored, mark_failed
from app.core.config import settings

@pytest.fixture
def mock_normalized_event():
    return NormalizedWebhookEvent(
        delivery_id=str(uuid.uuid4()),
        event_type="push",
        action=None,
        installation_id=12345,
        repository=RepoRef(github_repo_id=98765, full_name="test/repo"),
        installation_account_login="test",
        installation_account_type="Organization",
        repositories_removed=[],
        raw_payload={"mock": "payload"}
    )

def test_record_event_success(db_session: Session, mock_normalized_event: NormalizedWebhookEvent):
    repo_id = uuid.uuid4()
    
    event = record_event(db_session, mock_normalized_event, repo_id)
    
    assert event is not None
    assert event.delivery_id == mock_normalized_event.delivery_id
    assert event.event_type == mock_normalized_event.event_type
    assert event.action == mock_normalized_event.action
    assert event.status == "received"
    assert event.repository_id == repo_id
    assert event.processed_at is None
    
def test_record_event_duplicate_returns_none(db_session: Session, mock_normalized_event: NormalizedWebhookEvent):
    repo_id = uuid.uuid4()
    
    event1 = record_event(db_session, mock_normalized_event, repo_id)
    assert event1 is not None
    
    # Try inserting the same delivery_id again
    event2 = record_event(db_session, mock_normalized_event, repo_id)
    
    # Should cleanly return None, not raise IntegrityError
    assert event2 is None
    
    # Ensure only one is in the DB
    count = db_session.query(GitHubEvent).filter_by(delivery_id=mock_normalized_event.delivery_id).count()
    assert count == 1

def test_status_transitions(db_session: Session, mock_normalized_event: NormalizedWebhookEvent):
    event = record_event(db_session, mock_normalized_event, None)
    
    # Test ignored
    event_ignored = mark_ignored(db_session, event)
    assert event_ignored.status == "ignored"
    assert event_ignored.processed_at is not None
    
    # Test processed
    event_processed = mark_processed(db_session, event)
    assert event_processed.status == "processed"
    assert event_processed.processed_at is not None

def test_mark_failed_strips_secrets(db_session: Session, mock_normalized_event: NormalizedWebhookEvent):
    event = record_event(db_session, mock_normalized_event, None)
    
    # Ensure settings has a secret to strip
    original_secret = settings.GITHUB_WEBHOOK_SECRET
    settings.GITHUB_WEBHOOK_SECRET = "super_secret_webhook_token_value"
    
    try:
        error = Exception("Signature validation failed for super_secret_webhook_token_value: invalid hash")
        
        event_failed = mark_failed(db_session, event, error)
        
        assert event_failed.status == "failed"
        assert event_failed.processed_at is not None
        assert "super_secret_webhook_token_value" not in event_failed.error_message
        assert "***STRIPPED_SECRET***" in event_failed.error_message
    finally:
        settings.GITHUB_WEBHOOK_SECRET = original_secret

def test_concurrent_insert_race(SessionLocal, mock_normalized_event: NormalizedWebhookEvent):
    repo_id = uuid.uuid4()
    
    def insert_task():
        session = SessionLocal()
        try:
            return record_event(session, mock_normalized_event, repo_id)
        finally:
            session.close()

    # Clean up first to avoid false negatives from other tests run in the same session
    session = SessionLocal()
    session.query(GitHubEvent).filter_by(delivery_id=mock_normalized_event.delivery_id).delete()
    session.commit()
    session.close()

    # Run in parallel
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(insert_task) for _ in range(5)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())
    
    # Exactly one result should be a GitHubEvent, the rest should be None
    successes = [r for r in results if r is not None]
    assert len(successes) == 1
    assert successes[0].delivery_id == mock_normalized_event.delivery_id
    
    nones = [r for r in results if r is None]
    assert len(nones) == 4
    
    # Verify in DB
    session = SessionLocal()
    count = session.query(GitHubEvent).filter_by(delivery_id=mock_normalized_event.delivery_id).count()
    assert count == 1
    
    # Cleanup after test
    session.query(GitHubEvent).filter_by(delivery_id=mock_normalized_event.delivery_id).delete()
    session.commit()
    session.close()

