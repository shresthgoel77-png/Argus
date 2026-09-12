import pytest
from app.monitoring.analyzers.pull_request_analyzer import PullRequestAnalyzer
from app.monitoring.analyzer_base import AnalyzerContext
from app.integrations.github.webhook_events import NormalizedWebhookEvent, RepoRef
from app.models.repository import Repository

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
