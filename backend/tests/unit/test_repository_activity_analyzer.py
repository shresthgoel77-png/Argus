import pytest
from app.monitoring.analyzers.repository_activity_analyzer import RepositoryActivityAnalyzer
from app.monitoring.analyzer_base import AnalyzerContext
from app.integrations.github.webhook_events import NormalizedWebhookEvent, RepoRef
from app.models.repository import Repository

def create_context(event_type: str, ref: str | None = None, forced: bool | None = None, default_branch: str = "main") -> AnalyzerContext:
    ev = NormalizedWebhookEvent(
        delivery_id="del-1",
        event_type=event_type,
        action=None,
        installation_id=1,
        repository=RepoRef(github_repo_id=1, full_name="my/repo"),
        installation_account_login=None,
        installation_account_type=None,
        repositories_removed=[],
        raw_payload={},
        ref=ref,
        forced=forced,
    )
    repo = Repository(github_repo_id=1, full_name="my/repo", private=False, default_branch=default_branch, monitoring_enabled=True)
    return AnalyzerContext(repository=repo, normalized_event=ev)
    
def test_activity_analyzer_force_push_default_branch():
    analyzer = RepositoryActivityAnalyzer()
    ctx = create_context("push", ref="refs/heads/main", forced=True, default_branch="main")
    findings = analyzer.analyze(ctx)
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert findings[0].type_ == "force_push_default_branch"

def test_activity_analyzer_force_push_non_default_branch():
    analyzer = RepositoryActivityAnalyzer()
    ctx = create_context("push", ref="refs/heads/feature-branch", forced=True, default_branch="main")
    findings = analyzer.analyze(ctx)
    assert len(findings) == 0

def test_activity_analyzer_non_forced_push():
    analyzer = RepositoryActivityAnalyzer()
    ctx = create_context("push", ref="refs/heads/main", forced=False, default_branch="main")
    findings = analyzer.analyze(ctx)
    assert len(findings) == 0

def test_activity_analyzer_non_push_event():
    analyzer = RepositoryActivityAnalyzer()
    ctx = create_context("pull_request")
    findings = analyzer.analyze(ctx)
    assert len(findings) == 0
