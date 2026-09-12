import pytest
from unittest.mock import MagicMock
from app.models.user import User
from app.models.github_connection import GitHubConnection
from app.models.repository import Repository
from app.integrations.github.webhook_events import NormalizedWebhookEvent, RepoRef
from app.services.github_event_service import process_webhook_event
from app.monitoring import monitor_service

def test_process_webhook_event_analyzes_pull_request(db_session, monkeypatch):
    u = User(email="t4@a.com", display_name="T4", auth_provider="o", external_auth_id="4")
    db_session.add(u)
    db_session.commit()
    conn = GitHubConnection(user_id=u.id, installation_id=44444, account_login="org4", account_type="Organization", status="active")
    db_session.add(conn)
    db_session.commit()

    repo = Repository(connection_id=conn.id, github_repo_id=12399, full_name="org4/r", private=False, monitoring_enabled=True)
    db_session.add(repo)
    db_session.commit()
    
    mock_event = NormalizedWebhookEvent(
        delivery_id="pr-1",
        event_type="pull_request",
        action="opened",
        installation_id=44444,
        repository=RepoRef(github_repo_id=12399, full_name="org4/r"),
        installation_account_login="org4",
        installation_account_type="Organization",
        repositories_removed=[],
        raw_payload={"pull_request": {"body": None, "html_url": "foo", "number": 1}}
    )
    
    fake_run_analyzer_called = False
    
    async def fake_run_analyzer(db, analyzer_key, repository, normalized_event):
        nonlocal fake_run_analyzer_called
        assert analyzer_key == "pull_request"
        fake_run_analyzer_called = True
        return []
        
    monkeypatch.setattr(monitor_service, "run_analyzer", fake_run_analyzer)

    result = process_webhook_event(db_session, mock_event, MagicMock())
    assert result is not None
    assert result.status == "processed"
    assert fake_run_analyzer_called is True
