import pytest
from app.monitoring.analyzers.issue_analyzer import IssueAnalyzer
from app.monitoring.analyzer_base import AnalyzerContext
from app.integrations.github.webhook_events import NormalizedWebhookEvent, RepoRef
from app.models.repository import Repository

def create_context(
    event_type: str, 
    action: str, 
    issue_body: str | None,
    issue_number: int = 1,
    issue_url: str = "http://github.com/issue/1"
) -> AnalyzerContext:
    
    raw_payload = {}
    if event_type == "issues":
        raw_payload["issue"] = {
            "body": issue_body,
            "html_url": issue_url,
            "number": issue_number
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

def test_issue_analyzer_ignores_non_issue():
    analyzer = IssueAnalyzer()
    ctx = create_context("push", "opened", None)
    findings = analyzer.analyze(ctx)
    assert len(findings) == 0

def test_issue_analyzer_ignores_edited_action():
    analyzer = IssueAnalyzer()
    ctx = create_context("issues", "edited", None)
    findings = analyzer.analyze(ctx)
    assert len(findings) == 0

def test_issue_analyzer_ignores_non_empty_body():
    analyzer = IssueAnalyzer()
    ctx = create_context("issues", "opened", "This is a valid body")
    findings = analyzer.analyze(ctx)
    assert len(findings) == 0

def test_issue_analyzer_flags_empty_body_string():
    analyzer = IssueAnalyzer()
    ctx = create_context("issues", "opened", "   ")
    findings = analyzer.analyze(ctx)
    assert len(findings) == 1
    assert findings[0].severity == "info"
    assert findings[0].type_ == "issue_opened_without_description"
    assert findings[0].evidence["issue_number"] == 1

def test_issue_analyzer_flags_none_body():
    analyzer = IssueAnalyzer()
    ctx = create_context("issues", "opened", None)
    findings = analyzer.analyze(ctx)
    assert len(findings) == 1
    assert findings[0].severity == "info"
    assert findings[0].type_ == "issue_opened_without_description"
