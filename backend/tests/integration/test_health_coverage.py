"""Coverage, history and real runner regression tests with no external writes."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from app.integrations.github.client import GitHubAppClient
from app.integrations.github.exceptions import GitHubAPIError
from app.models.finding import Finding
from app.models.repository_health_snapshot import RepositoryHealthSnapshot
from app.schemas.health import HealthSnapshotResponse
from app.services import scheduled_monitoring_service as monitoring
from app.services.health_score_service import HEALTH_CATEGORY_TO_CHECK
from app.services.health_service import compute_and_persist_health, is_current_snapshot
from app.services.repository_summary_context_builder import build_repository_summary_context


def set_checks(repo, statuses):
    now = datetime.now(timezone.utc).isoformat()
    repo.monitoring_checks = {
        name: {"status": status, "checked_at": now, "error_message": None}
        for name, status in statuses.items()
    }
    repo.monitoring_status = "partial_failure"


def finding(repo, category, severity):
    return Finding(
        repository_id=repo.id, category=category, severity=severity,
        type="coverage_test", title="Test finding", description="Test evidence",
        status="open", source="test", evidence={},
    )


@pytest.mark.parametrize("excluded_status", ["failed", "unavailable", "pending", "running"])
def test_partial_score_excludes_stale_findings_and_persists_coverage(
    db_session, test_user_repository, excluded_status,
):
    repo = test_user_repository
    set_checks(repo, {"security": "success", "code_quality": "success", "ci_cd": excluded_status})
    db_session.add_all([
        finding(repo, "security", "critical"), finding(repo, "code_quality", "medium"),
        finding(repo, "ci", "critical"), finding(repo, "dependency", "critical"),
    ])
    db_session.commit()
    snapshot = compute_and_persist_health(db_session, repo.id)
    assert snapshot.category_scores == {"security": 60, "code_quality": 90}
    assert snapshot.overall_score == 75
    assert snapshot.coverage["excluded_categories"]["ci_cd"]["status"] == excluded_status
    coverage = snapshot.coverage
    db_session.expire_all()
    stored = db_session.get(RepositoryHealthSnapshot, snapshot.id)
    assert stored.coverage == coverage
    assert stored.category_scores == {"security": 60, "code_quality": 90}
    assert "_coverage" not in HealthSnapshotResponse.model_validate(stored).category_scores
    assert len(HealthSnapshotResponse.model_validate(stored).coverage.assessed_categories) == 2


def test_full_score_and_zero_coverage(db_session, test_user_repository):
    repo = test_user_repository
    set_checks(repo, {name: "success" for name in HEALTH_CATEGORY_TO_CHECK.values()})
    db_session.add(finding(repo, "security", "high"))
    db_session.commit()
    snapshot = compute_and_persist_health(db_session, repo.id)
    assert snapshot.overall_score == round((80 + 5 * 100) / 6)
    assert len(snapshot.category_scores) == 6
    assert len(snapshot.coverage["assessed_categories"]) == 6
    assert snapshot.coverage["excluded_categories"] == {}
    set_checks(repo, {name: "failed" for name in HEALTH_CATEGORY_TO_CHECK.values()})
    db_session.commit()
    assert compute_and_persist_health(db_session, repo.id) is None
    assert db_session.query(RepositoryHealthSnapshot).filter_by(repository_id=repo.id).count() == 1


@pytest.mark.asyncio
async def test_partial_dashboard_ai_and_new_run_history(authorized_client, db_session, test_user_repository):
    repo = test_user_repository
    set_checks(repo, {"security": "success", "health": "success"})
    db_session.commit()
    snapshot = compute_and_persist_health(db_session, repo.id)
    assert is_current_snapshot(repo, snapshot)
    data = (await authorized_client.get(f"/api/v1/repositories/{repo.id}/dashboard")).json()
    assert data["health"]["overall_score"] == 100
    assert data["monitoring_status"] == "partial_failure"
    assert len(data["health"]["coverage"]["assessed_categories"]) == 1
    assert data["needs_attention"]["health_snapshot"]["coverage"] == data["health"]["coverage"]
    assert data["last_recorded_health"] is None
    context = build_repository_summary_context(db_session, repo.id).untrusted_content
    assert "Overall Health Score: 100" in context
    assert "Health Coverage:" in context
    response = await authorized_client.get(f"/api/v1/repositories/{repo.id}/health")
    assert response.status_code == 200
    assert "1/6 categories assessed" in data["activity_feed"][0]["summary"]

    # A later failed run must not relabel the previous partial score as current.
    set_checks(repo, {"security": "failed", "health": "unavailable"})
    db_session.commit()
    data = (await authorized_client.get(f"/api/v1/repositories/{repo.id}/dashboard")).json()
    assert data["health"] is None
    assert data["last_recorded_health"]["overall_score"] == 100
    assert data["last_recorded_health"]["coverage"]["assessed_categories"] == ["security"]
    assert data["needs_attention"]["health_snapshot"] is None
    context = build_repository_summary_context(db_session, repo.id).untrusted_content
    assert "Overall Health Score: N/A" in context
    assert "Last recorded score (historical, not current): 100" in context
    assert (await authorized_client.get(f"/api/v1/repositories/{repo.id}/health")).status_code == 409


@pytest.mark.asyncio
async def test_legacy_snapshot_never_acquires_invented_coverage(authorized_client, db_session, test_user_repository):
    repo = test_user_repository
    set_checks(repo, {name: "success" for name in [*HEALTH_CATEGORY_TO_CHECK.values(), "health"]})
    repo.monitoring_status = "success"
    snapshot = RepositoryHealthSnapshot(repository_id=repo.id, overall_score=100, category_scores={"security": 100}, reasons=[])
    db_session.add(snapshot)
    db_session.commit()
    data = (await authorized_client.get(f"/api/v1/repositories/{repo.id}/dashboard")).json()
    assert data["health"] is None
    assert data["last_recorded_health"]["coverage"] is None
    assert data["last_recorded_health"]["computed_at"].endswith("Z")
    assert "coverage unknown" in data["activity_feed"][0]["summary"]
    assert snapshot.coverage is None


@pytest.mark.parametrize("status,message,expected", [
    (403, "Dependabot alerts are disabled for this repository.", "reports Dependabot alerts are disabled"),
    (403, "Resource not accessible by integration ghp_SECRET", "denied access"),
    (401, "Bad credentials ghp_SECRET", "rejected authentication"),
    (429, "Rate limit ghp_SECRET", "rate limit"),
    (403, "API rate limit exceeded ghp_SECRET", "rate limit"),
    (400, "Pagination using the page parameter is not supported ghp_SECRET", "rejected the Dependabot alerts request"),
    (500, "Unexpected upstream ghp_SECRET", "could not complete"),
    (None, "ghp_SECRET", "failed unexpectedly"),
])
@pytest.mark.asyncio
async def test_security_reasons_survive_runner_without_secrets(
    monkeypatch, db_session, test_user_repository, status, message, expected,
):
    error = (
        GitHubAPIError.from_response(httpx.Response(status, json={"message": message}))
        if status else ValueError(message)
    )
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.list_dependabot_alerts.side_effect = error
    client.list_repository_workflow_runs.return_value = []
    monkeypatch.setattr(monitoring, "GitHubAppClient", lambda *a, **kw: client)
    monkeypatch.setattr("app.monitoring.monitor_service.GitHubAppClient", lambda *a, **kw: client)
    monkeypatch.setattr(monitoring.IssueAnalyzer, "scan_repository_for_stale_issues", AsyncMock())
    monkeypatch.setattr(monitoring.PullRequestAnalyzer, "scan_repository_for_stale_prs", AsyncMock())
    monkeypatch.setattr("app.monitoring.analyzers.dependency_analyzer.DependencyAnalyzer.analyze", AsyncMock(return_value=[]))
    monkeypatch.setattr("app.monitoring.analyzers.code_quality_analyzer.CodeQualityAnalyzer.analyze", AsyncMock(return_value=[]))
    result = await monitoring.run_monitoring_checks_for_repository(db_session, test_user_repository)
    security = result.checks["security"]
    assert security.status == "failed"
    assert expected in security.error_message
    assert "ghp_SECRET" not in security.error_message
    assert test_user_repository.monitoring_checks["security"]["error_message"] == security.error_message
    assert result.checks["health"].status == "success"
    assert result.status == "partial_failure"


@pytest.mark.asyncio
async def test_empty_dependabot_and_no_ci_produce_five_category_score(monkeypatch, db_session, test_user_repository):
    requests = []

    def respond(request):
        assert request.method == "GET", "Verification must never publish GitHub resources"
        requests.append(request.url.path)
        if request.url.path.endswith("/dependabot/alerts"):
            assert "page" not in request.url.params
            return httpx.Response(200, json=[])
        if request.url.path.endswith("/actions/runs"):
            return httpx.Response(200, json={"total_count": 0, "workflow_runs": []})
        if request.url.path.endswith(("/issues", "/pulls")):
            return httpx.Response(200, json=[])
        if request.url.path.endswith("/contents/package.json"):
            return httpx.Response(404, json={"message": "Not found"})
        return httpx.Response(200, json={"full_name": test_user_repository.full_name})

    class Client(GitHubAppClient):
        async def __aenter__(self):
            self._http = httpx.AsyncClient(base_url="https://api.github.com", transport=httpx.MockTransport(respond))
            return self

        async def _auth_headers(self, **kwargs):
            return {}

    monkeypatch.setattr(monitoring, "GitHubAppClient", Client)
    monkeypatch.setattr("app.monitoring.monitor_service.GitHubAppClient", Client)
    monkeypatch.setattr("app.monitoring.analyzers.code_quality_analyzer.get_branch_protection", AsyncMock(return_value=None))
    no_ai = Mock(side_effect=AssertionError("Assessment must not call AI"))
    monkeypatch.setattr("app.services.ai_analysis_service.request_repository_summary", no_ai)
    result = await monitoring.run_monitoring_checks_for_repository(db_session, test_user_repository)
    assert result.checks["security"].status == "success"
    assert result.checks["ci_cd"].status == "unavailable"
    assert result.checks["ci_cd"].error_message == "GitHub has no workflow-run history to assess."
    assert result.checks["health"].status == "success"
    assert result.status == "partial_failure"
    snapshot = db_session.query(RepositoryHealthSnapshot).filter_by(repository_id=test_user_repository.id).one()
    assert snapshot.overall_score == 98
    assert snapshot.category_scores["code_quality"] == 90
    assert "ci_cd" not in snapshot.category_scores
    assert len(snapshot.coverage["assessed_categories"]) == 5
    assert is_current_snapshot(test_user_repository, snapshot)
    assert any(path.endswith("/dependabot/alerts") for path in requests)
    no_ai.assert_not_called()
