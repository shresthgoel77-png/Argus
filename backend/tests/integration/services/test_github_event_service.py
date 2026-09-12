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
from app.services.github_event_service import process_webhook_event
from app.models.github_connection import GitHubConnection
from unittest.mock import MagicMock

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
    original_secret = settings.github_app_webhook_secret
    from pydantic import SecretStr
    settings.github_app_webhook_secret = SecretStr("super_secret_webhook_token_value")
    
    try:
        error = Exception("Signature validation failed for super_secret_webhook_token_value: invalid hash")
        
        event_failed = mark_failed(db_session, event, error)
        
        assert event_failed.status == "failed"
        assert event_failed.processed_at is not None
        assert "super_secret_webhook_token_value" not in event_failed.error_message
        assert "***STRIPPED_SECRET***" in event_failed.error_message
    finally:
        settings.github_app_webhook_secret = original_secret

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


def test_process_webhook_event_duplicate(db_session):
    # insert an event directly
    event = GitHubEvent(delivery_id="dup-1", event_type="push", payload={}, status="processed")
    db_session.add(event)
    db_session.commit()
    
    mock_event = NormalizedWebhookEvent(
        delivery_id="dup-1",
        event_type="push",
        action=None,
        installation_id=None,
        repository=None,
        installation_account_login=None,
        installation_account_type=None,
        repositories_removed=[],
        raw_payload={}
    )
    result = process_webhook_event(db_session, mock_event, MagicMock())
    assert result is None

def test_process_webhook_event_unknown_installation(db_session):
    mock_event = NormalizedWebhookEvent(
        delivery_id="unknown-1",
        event_type="installation",
        action="created",
        installation_id=99999,
        repository=None,
        installation_account_login="org1",
        installation_account_type="Organization",
        repositories_removed=[],
        raw_payload={}
    )
    result = process_webhook_event(db_session, mock_event, MagicMock())
    assert result is not None
    assert result.status == "ignored"

def test_process_webhook_event_known_installation_suspend(db_session):
    u = User(email="test@a.com", display_name="Test", auth_provider="o", external_auth_id="1")
    db_session.add(u)
    db_session.commit()
    conn = GitHubConnection(user_id=u.id, installation_id=11111, account_login="org1", account_type="Organization", status="active")
    db_session.add(conn)
    db_session.commit()
    
    mock_event = NormalizedWebhookEvent(
        delivery_id="known-1",
        event_type="installation",
        action="suspend",
        installation_id=11111,
        repository=None,
        installation_account_login="org1",
        installation_account_type="Organization",
        repositories_removed=[],
        raw_payload={}
    )
    
    result = process_webhook_event(db_session, mock_event, MagicMock())
    assert result is not None
    assert result.status == "processed"
    
    db_session.refresh(conn)
    assert conn.status == "suspended"

def test_process_webhook_event_removed_repos(db_session):
    u = User(email="t2@a.com", display_name="T2", auth_provider="o", external_auth_id="2")
    db_session.add(u)
    db_session.commit()
    conn = GitHubConnection(user_id=u.id, installation_id=22222, account_login="org2", account_type="Organization", status="active")
    db_session.add(conn)
    db_session.commit()
    
    repo = Repository(connection_id=conn.id, github_repo_id=12345, full_name="org2/r", private=False, monitoring_enabled=True)
    db_session.add(repo)
    db_session.commit()
    
    mock_event = NormalizedWebhookEvent(
        delivery_id="repo-rem-1",
        event_type="installation_repositories",
        action="removed",
        installation_id=22222,
        repository=None,
        installation_account_login="org2",
        installation_account_type="Organization",
        repositories_removed=[RepoRef(github_repo_id=12345, full_name="org2/r")],
        raw_payload={}
    )
    
    result = process_webhook_event(db_session, mock_event, MagicMock())
    assert result is not None
    assert result.status == "processed"
    
    db_session.refresh(repo)
    assert repo.monitoring_enabled is False

def test_process_webhook_event_reaction_failure_marks_failed(db_session, monkeypatch):
    u = User(email="t3@a.com", display_name="T3", auth_provider="o", external_auth_id="3")
    db_session.add(u)
    db_session.commit()
    conn = GitHubConnection(user_id=u.id, installation_id=33333, account_login="org3", account_type="Organization", status="active")
    db_session.add(conn)
    db_session.commit()

    import app.services.github_event_service
    def fake_handler(*args, **kwargs):
        raise ValueError("Simulated reaction failure")
        
    monkeypatch.setattr(app.services.github_event_service, "handle_installation_status_change", fake_handler)
    
    mock_event = NormalizedWebhookEvent(
        delivery_id="fail-1",
        event_type="installation",
        action="suspend",
        installation_id=33333,
        repository=None,
        installation_account_login="org3",
        installation_account_type="Organization",
        repositories_removed=[],
        raw_payload={}
    )
    
    result = process_webhook_event(db_session, mock_event, MagicMock())
    assert result is not None
    assert result.status == "failed"
    assert "Simulated reaction failure" in result.error_message
