import pytest
import uuid
from unittest.mock import patch
from app.monitoring.monitor_service import run_analyzer
from app.monitoring.analyzer_base import BaseAnalyzer, AnalyzerContext, FindingDraft
from app.models.finding import Finding
from app.models.repository_health_snapshot import RepositoryHealthSnapshot
import app.monitoring.analyzers as analyzers_registry

class DummySuccessAnalyzer(BaseAnalyzer):
    key = "dummy_success"
    category = "security"
    requires_client = False
    def analyze(self, context: AnalyzerContext) -> list[FindingDraft]:
        return [
            FindingDraft(
                category="security",
                type_="exposed_secret",
                title="Found a secret",
                description="A secret was found",
                severity="high",
                evidence={"line": 42}
            )
        ]

class DummyErrorAnalyzer(BaseAnalyzer):
    key = "dummy_error"
    category = "security"
    requires_client = False
    
    def analyze(self, context: AnalyzerContext) -> list[FindingDraft]:
        raise ValueError("Something went wrong in the analyzer")


class DummyFullStateAnalyzer(BaseAnalyzer):
    key = "dummy_full_state"
    category = "security"
    requires_client = False
    full_state_sync = True

    def analyze(self, context: AnalyzerContext) -> list[FindingDraft]:
        return [
            FindingDraft(
                category="security",
                type_="exposed_secret",
                title="Full-state finding",
                description="A full-state finding was found",
                severity="high",
                evidence={"line": 7},
                fingerprint="dummy-full-state-fingerprint",
            )
        ]

@pytest.fixture(autouse=True)
def register_dummy_analyzers():
    analyzers_registry.ANALYZER_REGISTRY["dummy_success"] = DummySuccessAnalyzer()
    analyzers_registry.ANALYZER_REGISTRY["dummy_error"] = DummyErrorAnalyzer()
    analyzers_registry.ANALYZER_REGISTRY["dummy_full_state"] = DummyFullStateAnalyzer()
    yield
    analyzers_registry.ANALYZER_REGISTRY.pop("dummy_success", None)
    analyzers_registry.ANALYZER_REGISTRY.pop("dummy_error", None)
    analyzers_registry.ANALYZER_REGISTRY.pop("dummy_full_state", None)


@pytest.mark.asyncio
async def test_run_analyzer_skipped_when_monitoring_disabled(db_session, test_user_repository):
    test_user_repository.monitoring_enabled = False
    db_session.commit()
    db_session.refresh(test_user_repository)
    
    result = await run_analyzer(db_session, "dummy_success", test_user_repository)
    assert result.status == "skipped"
    assert result.reason == "monitoring_disabled"

@pytest.mark.asyncio
async def test_run_analyzer_unknown_analyzer(db_session, test_user_repository):
    test_user_repository.monitoring_enabled = True
    db_session.commit()
    
    result = await run_analyzer(db_session, "unknown_key", test_user_repository)
    assert result.status == "skipped"
    assert result.reason == "unknown_analyzer"

@pytest.mark.asyncio
async def test_run_analyzer_exception_containment(db_session, test_user_repository):
    test_user_repository.monitoring_enabled = True
    db_session.commit()
    
    result = await run_analyzer(db_session, "dummy_error", test_user_repository)
    assert result.status == "failed"
    assert result.error_message == "The analyzer could not be completed."

@pytest.mark.asyncio
async def test_run_analyzer_success_persists_findings(db_session, test_user_repository):
    test_user_repository.monitoring_enabled = True
    db_session.commit()
    
    result = await run_analyzer(db_session, "dummy_success", test_user_repository)
    assert result.status == "success"
    assert len(result.findings_created) == 1
    
    finding = result.findings_created[0]
    assert finding.title == "Found a secret"
    assert finding.category == "security"


@pytest.mark.asyncio
async def test_run_analyzer_full_state_uses_sync_result(db_session, test_user_repository):
    test_user_repository.monitoring_enabled = True
    db_session.commit()

    result = await run_analyzer(db_session, "dummy_full_state", test_user_repository)

    assert result.status == "success"
    assert result.findings_created == []
    assert result.sync_result is not None
    assert result.sync_result.created == 1
    assert result.sync_result.updated == 0
    assert result.sync_result.auto_resolved == 0

    second_result = await run_analyzer(
        db_session, "dummy_full_state", test_user_repository
    )

    assert second_result.sync_result is not None
    assert second_result.sync_result.created == 0
    assert second_result.sync_result.updated == 1
    assert db_session.query(Finding).filter(Finding.repository_id == test_user_repository.id).count() == 1



@pytest.mark.asyncio
async def test_run_analyzer_success_computes_health(db_session, test_user_repository):
    test_user_repository.monitoring_enabled = True
    test_user_repository.monitoring_status = "success"
    test_user_repository.monitoring_checks = {
        name: {"status": "success"}
        for name in (
            "ci_cd",
            "stale_issues",
            "stale_prs",
            "dependency",
            "security",
            "code_quality",
        )
    }
    db_session.commit()
    
    # Pre-check
    snapshots = db_session.query(RepositoryHealthSnapshot).filter_by(repository_id=test_user_repository.id).all()
    assert len(snapshots) == 0

    result = await run_analyzer(db_session, "dummy_success", test_user_repository)
    assert result.status == "success"
    
    snapshots = db_session.query(RepositoryHealthSnapshot).filter_by(repository_id=test_user_repository.id).all()
    assert len(snapshots) == 1
    assert snapshots[0].category_scores["security"] == 80
    assert snapshots[0].overall_score < 100


@pytest.mark.asyncio
async def test_permission_failure_never_resolves_full_state_findings(
    db_session, test_user_repository, monkeypatch
):
    from app.integrations.github.exceptions import GitHubAuthError

    test_user_repository.monitoring_enabled = True
    db_session.add(
        Finding(
            repository_id=test_user_repository.id,
            category="dependency",
            type="missing_lockfile",
            title="Existing dependency finding",
            description="Existing open finding",
            severity="medium",
            status="open",
            source="test",
            evidence={},
            fingerprint=f"dependency:{test_user_repository.id}:package.json",
        )
    )
    db_session.commit()

    class ForbiddenClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get_repository_content(self, *args):
            raise GitHubAuthError("permission denied", response_status=403)

    monkeypatch.setattr(
        "app.monitoring.monitor_service.GitHubAppClient",
        lambda **kwargs: ForbiddenClient(),
    )

    result = await run_analyzer(
        db_session, "dependency", test_user_repository
    )

    db_session.refresh(
        db_session.query(Finding)
        .filter(Finding.repository_id == test_user_repository.id)
        .one()
    )
    finding = (
        db_session.query(Finding)
        .filter(Finding.repository_id == test_user_repository.id)
        .one()
    )
    assert result.status == "failed"
    assert finding.status == "open"


@pytest.mark.asyncio
async def test_run_analyzer_exception_no_health_recomputation(db_session, test_user_repository):
    test_user_repository.monitoring_enabled = True
    db_session.commit()
    
    result = await run_analyzer(db_session, "dummy_error", test_user_repository)
    assert result.status == "failed"
    
    snapshots = db_session.query(RepositoryHealthSnapshot).filter_by(repository_id=test_user_repository.id).all()
    assert len(snapshots) == 0


@patch("app.monitoring.monitor_service.compute_and_persist_health")
@pytest.mark.asyncio
async def test_run_analyzer_health_exception_swallowed(mock_health, db_session, test_user_repository):
    test_user_repository.monitoring_enabled = True
    db_session.commit()
    
    mock_health.side_effect = Exception("Mocked health computation failure")
    
    result = await run_analyzer(db_session, "dummy_success", test_user_repository)
    
    # analyzer result shouldn't be affected
    assert result.status == "success"
    mock_health.assert_called_once_with(db_session, test_user_repository.id)
