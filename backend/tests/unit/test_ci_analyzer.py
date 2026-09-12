import pytest
from app.monitoring.analyzers.ci_analyzer import CIAnalyzer
from app.monitoring.analyzer_base import AnalyzerContext
from app.integrations.github.webhook_events import NormalizedWebhookEvent, RepoRef
from app.models.repository import Repository

def create_context(event_type: str, action: str, conclusion: str, name: str = "CI") -> AnalyzerContext:
    ev = NormalizedWebhookEvent(
        delivery_id="del-1",
        event_type=event_type,
        action=action,
        installation_id=1,
        repository=RepoRef(github_repo_id=1, full_name="my/repo"),
        installation_account_login=None,
        installation_account_type=None,
        repositories_removed=[],
        raw_payload={},
        workflow_run_id=100,
        workflow_run_name=name,
        workflow_run_conclusion=conclusion,
        workflow_run_url="http://example.com",
    )
    repo = Repository(github_repo_id=1, full_name="my/repo", private=False, monitoring_enabled=True)
    return AnalyzerContext(repository=repo, normalized_event=ev)
    
def test_ci_analyzer_ignores_non_workflow_run():
    analyzer = CIAnalyzer()
    ctx = create_context("push", "completed", "success")
    findings = analyzer.analyze(ctx)
    assert len(findings) == 0

def test_ci_analyzer_ignores_non_completed():
    analyzer = CIAnalyzer()
    ctx = create_context("workflow_run", "requested", "success")
    findings = analyzer.analyze(ctx)
    assert len(findings) == 0

def test_ci_analyzer_ignores_success():
    analyzer = CIAnalyzer()
    ctx = create_context("workflow_run", "completed", "success")
    findings = analyzer.analyze(ctx)
    assert len(findings) == 0

def test_ci_analyzer_failure_gives_high_severity():
    analyzer = CIAnalyzer()
    ctx = create_context("workflow_run", "completed", "failure")
    findings = analyzer.analyze(ctx)
    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert findings[0].type_ == "workflow_run_failed"

def test_ci_analyzer_cancelled_gives_low_severity():
    analyzer = CIAnalyzer()
    ctx = create_context("workflow_run", "completed", "cancelled")
    findings = analyzer.analyze(ctx)
    assert len(findings) == 1
    assert findings[0].severity == "low"
    assert findings[0].type_ == "workflow_run_cancelled"
