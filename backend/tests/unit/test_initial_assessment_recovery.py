from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.orm import sessionmaker

from app.models.repository import Repository
from app.services import scheduled_monitoring_service as service


@pytest.fixture
def isolated_runner_sessions(monkeypatch, db_session):
    # Share only the disposable test transaction, never the application's engine.
    factory = sessionmaker(bind=db_session.connection(), join_transaction_mode="create_savepoint")
    monkeypatch.setattr(service, "SessionLocal", factory)


@pytest.mark.asyncio
async def test_application_startup_resumes_queued_work_without_blocking_startup(monkeypatch):
    import app.main as main
    resume = Mock()
    monkeypatch.setattr(main.settings, "app_env", "development")
    monkeypatch.setattr(main, "resume_queued_initial_assessments", resume)

    await main.startup_event()
    await main.app.state.initial_assessment_recovery

    resume.assert_called_once_with()


@pytest.mark.asyncio
async def test_test_client_startup_does_not_scan_application_database(monkeypatch):
    import app.main as main
    resume = Mock()
    monkeypatch.setattr(main.settings, "app_env", "test")
    monkeypatch.setattr(main, "resume_queued_initial_assessments", resume)

    await main.startup_event()

    resume.assert_not_called()


def test_recovery_selects_only_enabled_queued_repositories(
    monkeypatch, db_session, test_user_repository, isolated_runner_sessions
):
    repo = test_user_repository
    repo.monitoring_status = "queued"
    repo.monitoring_checks = {}  # Exact migration-backfill state.
    db_session.add_all([
        Repository(connection_id=repo.connection_id, github_repo_id=98701,
                   full_name="test/disabled", monitoring_enabled=False, monitoring_status="queued"),
        Repository(connection_id=repo.connection_id, github_repo_id=98702,
                   full_name="test/running", monitoring_enabled=True, monitoring_status="running"),
        Repository(connection_id=repo.connection_id, github_repo_id=98703,
                   full_name="test/success", monitoring_enabled=True, monitoring_status="success"),
    ])
    db_session.commit()
    run = Mock()
    monkeypatch.setattr(service, "run_initial_assessment_in_background", run)

    service.resume_queued_initial_assessments()

    run.assert_called_once_with(str(repo.id))


@pytest.mark.parametrize("status,enabled", [("running", True), ("success", True), ("queued", False)])
def test_initial_runner_does_not_claim_ineligible_repository(
    monkeypatch, db_session, test_user_repository, isolated_runner_sessions, status, enabled
):
    repo = test_user_repository
    repo.monitoring_status, repo.monitoring_enabled = status, enabled
    db_session.commit()
    run = AsyncMock()
    monkeypatch.setattr(service, "run_monitoring_checks_for_repository", run)

    service.run_initial_assessment_in_background(str(repo.id))

    run.assert_not_called()
    db_session.refresh(repo)
    assert repo.monitoring_status == status


def test_queued_assessment_is_claimed_once_and_completes_without_ai(
    monkeypatch, db_session, test_user_repository, isolated_runner_sessions
):
    repo = test_user_repository
    repo.monitoring_status = "queued"
    db_session.commit()

    async def complete(db, repository):
        assert repository.monitoring_status == "running"
        repository.monitoring_status = "success"
        db.commit()

    run = AsyncMock(side_effect=complete)
    monkeypatch.setattr(service, "run_monitoring_checks_for_repository", run)
    monkeypatch.setattr("app.services.ai_analysis_service.request_repository_summary",
                        Mock(side_effect=AssertionError("AI must remain optional")))

    service.run_initial_assessment_in_background(str(repo.id))
    service.run_initial_assessment_in_background(str(repo.id))

    run.assert_awaited_once()
    db_session.refresh(repo)
    assert repo.monitoring_status == "success"


def test_recovery_continues_after_one_repository_fails(
    monkeypatch, db_session, test_user_repository, isolated_runner_sessions
):
    repo = test_user_repository
    repo.monitoring_status = "queued"
    db_session.add(Repository(
        connection_id=repo.connection_id, github_repo_id=98704, full_name="test/other",
        monitoring_enabled=True, monitoring_status="queued",
    ))
    db_session.commit()
    run = Mock(side_effect=[RuntimeError("failed assessment"), None])
    monkeypatch.setattr(service, "run_initial_assessment_in_background", run)

    service.resume_queued_initial_assessments()

    assert run.call_count == 2


def test_unexpected_failure_is_persisted_as_terminal_failure(
    monkeypatch, db_session, test_user_repository, isolated_runner_sessions
):
    repo = test_user_repository
    repo.monitoring_status = "queued"
    db_session.commit()
    monkeypatch.setattr(service, "run_monitoring_checks_for_repository",
                        AsyncMock(side_effect=RuntimeError("unexpected failure")))

    with pytest.raises(RuntimeError, match="unexpected failure"):
        service.run_initial_assessment_in_background(str(repo.id))

    db_session.refresh(repo)
    assert repo.monitoring_status == "failed"
    assert repo.monitoring_checks["assessment"]["status"] == "failed"
    assert repo.last_monitoring_at is not None


@pytest.mark.asyncio
async def test_real_analyzers_persist_findings_health_and_terminal_state_without_ai(
    monkeypatch, db_session, test_user_repository
):
    from unittest.mock import MagicMock
    from app.models.finding import Finding
    from app.models.repository_health_snapshot import RepositoryHealthSnapshot

    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.list_repository_issues = AsyncMock(return_value=[])
    client.list_repository_pulls = AsyncMock(return_value=[])
    client.list_dependabot_alerts = AsyncMock(return_value=[])
    client.list_repository_workflow_runs = AsyncMock(return_value=[{
        "workflow_id": 1, "id": 2, "status": "completed", "conclusion": "success",
    }])
    client.get_repository_content = AsyncMock(
        side_effect=lambda name, path: {"name": path} if path == "package.json" else None
    )
    monkeypatch.setattr(service, "GitHubAppClient", lambda *a, **kw: client)
    monkeypatch.setattr("app.monitoring.monitor_service.GitHubAppClient", lambda **kw: client)
    monkeypatch.setattr("app.monitoring.analyzers.code_quality_analyzer.get_branch_protection",
                        AsyncMock(return_value=None))
    ai = Mock(side_effect=AssertionError("AI must remain optional"))
    monkeypatch.setattr("app.services.ai_analysis_service.request_repository_summary", ai)

    result = await service.run_monitoring_checks_for_repository(db_session, test_user_repository)

    assert result.status == "success"
    assert test_user_repository.monitoring_status == "success"
    assert all(check.status == "success" for check in result.checks.values())
    findings = db_session.query(Finding).filter_by(repository_id=test_user_repository.id).all()
    assert {finding.type for finding in findings} == {"missing_lockfile", "missing_branch_protection"}
    assert all(finding.evidence and finding.severity == "medium" for finding in findings)
    snapshot = db_session.query(RepositoryHealthSnapshot).filter_by(
        repository_id=test_user_repository.id
    ).one()
    assert 0 < snapshot.overall_score < 100
    assert test_user_repository.last_monitoring_at is not None
    ai.assert_not_called()
