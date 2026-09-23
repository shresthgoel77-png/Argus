import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta
from app.monitoring.analyzers.pull_request_analyzer import PullRequestAnalyzer
from app.monitoring.analyzer_base import AnalyzerContext
from app.integrations.github.webhook_events import NormalizedWebhookEvent, RepoRef
from app.models.repository import Repository
import app.monitoring.analyzers.pull_request_analyzer as pr_analyzer_mdl
def create_context(
    event_type: str, 
    action: str, 
    pr_body: str | None,
    pr_number: int = 1,
    pr_url: str = "http://github.com/pr/1"
) -> AnalyzerContext:
    
    raw_payload = {}
    if event_type == "pull_request":
        raw_payload["pull_request"] = {
            "body": pr_body,
            "html_url": pr_url,
            "number": pr_number
        }
        
    ev = NormalizedWebhookEvent(
        delivery_id="del-1",
        event_type=event_type,
        action=action,
        installation_id=1,
        repository=RepoRef(github_repo_id=1, full_name="my/repo"),
        installation_account_login=None,
        installation_account_type=None,
        repositories_removed=[],
        raw_payload=raw_payload,
    )
    repo = Repository(github_repo_id=1, full_name="my/repo", private=False, monitoring_enabled=True)
    return AnalyzerContext(repository=repo, normalized_event=ev)

def test_pr_analyzer_ignores_non_pull_request():
    analyzer = PullRequestAnalyzer()
    ctx = create_context("push", "opened", None)
    findings = analyzer.analyze(ctx)
    assert len(findings) == 0

def test_pr_analyzer_ignores_edited_action():
    analyzer = PullRequestAnalyzer()
    ctx = create_context("pull_request", "edited", None)
    findings = analyzer.analyze(ctx)
    assert len(findings) == 0

def test_pr_analyzer_ignores_non_empty_body():
    analyzer = PullRequestAnalyzer()
    ctx = create_context("pull_request", "opened", "This is a valid body")
    findings = analyzer.analyze(ctx)
    assert len(findings) == 0

def test_pr_analyzer_flags_empty_body_string():
    analyzer = PullRequestAnalyzer()
    ctx = create_context("pull_request", "opened", "   ")
    findings = analyzer.analyze(ctx)
    assert len(findings) == 1
    assert findings[0].severity == "info"
    assert findings[0].type_ == "pull_request_opened_without_description"
    assert findings[0].evidence["pull_request_number"] == 1

def test_pr_analyzer_flags_none_body():
    analyzer = PullRequestAnalyzer()
    ctx = create_context("pull_request", "opened", None)
    findings = analyzer.analyze(ctx)
    assert len(findings) == 1
    assert findings[0].severity == "info"
    assert findings[0].type_ == "pull_request_opened_without_description"

@pytest.mark.asyncio
async def test_scan_repository_for_stale_prs():
    analyzer = PullRequestAnalyzer()
    db = MagicMock()
    import uuid
    repo = Repository(id=uuid.uuid4(), github_repo_id=1, full_name="my/repo")
    client = AsyncMock()
    
    stale_date = datetime.now(timezone.utc) - timedelta(days=20)
    fresh_date = datetime.now(timezone.utc) - timedelta(days=5)
    
    client.list_repository_pulls.return_value = [
        {"number": 1, "updated_at": stale_date.isoformat(), "html_url": "url1"},
        {"number": 2, "updated_at": fresh_date.isoformat(), "html_url": "url2"}
    ]
    
    original_finding_service = pr_analyzer_mdl.finding_service
    pr_analyzer_mdl.finding_service = MagicMock()
    
    try:
        await analyzer.scan_repository_for_stale_prs(db, repo, client)
        
        client.list_repository_pulls.assert_called_once_with("my/repo")
        pr_analyzer_mdl.finding_service.create_finding.assert_called_once()
        kwargs = pr_analyzer_mdl.finding_service.create_finding.call_args.kwargs
        assert kwargs["fingerprint"] == "stale_pull_request_1"
        assert kwargs["type_"] == "stale_pull_request"
        assert kwargs["severity"] == "info"
    finally:
        pr_analyzer_mdl.finding_service = original_finding_service
