from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.scheduled_monitoring_service import (
    run_monitoring_checks_for_repository,
)


@pytest.fixture
def enabled_repository(db_session, test_user_repository):
    test_user_repository.monitoring_enabled = True
    db_session.commit()
    return test_user_repository


def monitoring_mocks():
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    issue_analyzer = MagicMock()
    issue_analyzer.scan_repository_for_stale_issues = AsyncMock()
    pull_request_analyzer = MagicMock()
    pull_request_analyzer.scan_repository_for_stale_prs = AsyncMock()

    return client, issue_analyzer, pull_request_analyzer


@pytest.mark.asyncio
async def test_all_monitoring_checks_run_for_healthy_repository(
    db_session, enabled_repository
):
    client, issue_analyzer, pull_request_analyzer = monitoring_mocks()
    with (
        patch(
            "app.services.scheduled_monitoring_service.GitHubAppClient",
            return_value=client,
        ),
        patch(
            "app.services.scheduled_monitoring_service.IssueAnalyzer",
            return_value=issue_analyzer,
        ),
        patch(
            "app.services.scheduled_monitoring_service.PullRequestAnalyzer",
            return_value=pull_request_analyzer,
        ),
        patch(
            "app.services.scheduled_monitoring_service.run_analyzer",
            new=AsyncMock(
                return_value=SimpleNamespace(status="success")
            ),
        ) as run_analyzer,
        patch(
            "app.services.scheduled_monitoring_service."
            "compute_and_persist_health"
        ) as compute_health,
    ):
        result = await run_monitoring_checks_for_repository(
            db_session, enabled_repository
        )

    assert result.status == "success"
    assert set(result.checks) == {
        "stale_issues",
        "stale_prs",
        "dependency",
        "security",
        "code_quality",
        "health",
    }
    assert all(check.status == "success" for check in result.checks.values())
    issue_analyzer.scan_repository_for_stale_issues.assert_awaited_once()
    pull_request_analyzer.scan_repository_for_stale_prs.assert_awaited_once()
    assert run_analyzer.await_count == 3
    compute_health.assert_called_once_with(
        db_session, enabled_repository.id
    )


@pytest.mark.asyncio
async def test_monitoring_check_failure_does_not_block_remaining_checks(
    db_session, enabled_repository
):
    client, issue_analyzer, pull_request_analyzer = monitoring_mocks()
    issue_analyzer.scan_repository_for_stale_issues.side_effect = RuntimeError(
        "stale issue failure"
    )
    with (
        patch(
            "app.services.scheduled_monitoring_service.GitHubAppClient",
            return_value=client,
        ),
        patch(
            "app.services.scheduled_monitoring_service.IssueAnalyzer",
            return_value=issue_analyzer,
        ),
        patch(
            "app.services.scheduled_monitoring_service.PullRequestAnalyzer",
            return_value=pull_request_analyzer,
        ),
        patch(
            "app.services.scheduled_monitoring_service.run_analyzer",
            new=AsyncMock(
                return_value=SimpleNamespace(status="success")
            ),
        ),
        patch(
            "app.services.scheduled_monitoring_service."
            "compute_and_persist_health"
        ),
    ):
        result = await run_monitoring_checks_for_repository(
            db_session, enabled_repository
        )

    assert result.status == "partial_failure"
    assert result.checks["stale_issues"].status == "failed"
    assert (
        result.checks["stale_issues"].error_message == "stale issue failure"
    )
    assert all(
        result.checks[name].status == "success"
        for name in result.checks
        if name != "stale_issues"
    )
    pull_request_analyzer.scan_repository_for_stale_prs.assert_awaited_once()


@pytest.mark.asyncio
async def test_monitoring_service_never_raises_when_a_check_fails(
    db_session, enabled_repository
):
    client, issue_analyzer, pull_request_analyzer = monitoring_mocks()
    pull_request_analyzer.scan_repository_for_stale_prs.side_effect = (
        RuntimeError("stale PR failure")
    )
    with (
        patch(
            "app.services.scheduled_monitoring_service.GitHubAppClient",
            return_value=client,
        ),
        patch(
            "app.services.scheduled_monitoring_service.IssueAnalyzer",
            return_value=issue_analyzer,
        ),
        patch(
            "app.services.scheduled_monitoring_service.PullRequestAnalyzer",
            return_value=pull_request_analyzer,
        ),
        patch(
            "app.services.scheduled_monitoring_service.run_analyzer",
            new=AsyncMock(
                side_effect=RuntimeError(
                    "analyzer failure"
                )
            ),
        ),
        patch(
            "app.services.scheduled_monitoring_service."
            "compute_and_persist_health",
            side_effect=RuntimeError("health failure"),
        ),
    ):
        result = await run_monitoring_checks_for_repository(
            db_session, enabled_repository
        )

    assert result.status == "partial_failure"
    assert set(result.checks) == {
        "stale_issues",
        "stale_prs",
        "dependency",
        "security",
        "code_quality",
        "health",
    }
    assert result.checks["stale_issues"].status == "success"
    assert result.checks["stale_prs"].status == "failed"
    assert all(
        result.checks[name].status == "failed"
        for name in ("dependency", "security", "code_quality", "health")
    )


@pytest.mark.asyncio
async def test_monitoring_logs_reuse_one_correlation_id(
    db_session, enabled_repository
):
    client, issue_analyzer, pull_request_analyzer = monitoring_mocks()
    with (
        patch("app.services.scheduled_monitoring_service.logger") as logger,
        patch(
            "app.services.scheduled_monitoring_service.GitHubAppClient",
            return_value=client,
        ),
        patch(
            "app.services.scheduled_monitoring_service.IssueAnalyzer",
            return_value=issue_analyzer,
        ),
        patch(
            "app.services.scheduled_monitoring_service.PullRequestAnalyzer",
            return_value=pull_request_analyzer,
        ),
        patch(
            "app.services.scheduled_monitoring_service.run_analyzer",
            new=AsyncMock(
                return_value=SimpleNamespace(status="success")
            ),
        ),
        patch(
            "app.services.scheduled_monitoring_service."
            "compute_and_persist_health"
        ),
    ):
        result = await run_monitoring_checks_for_repository(
            db_session, enabled_repository
        )

    log_calls = [*logger.info.call_args_list, *logger.error.call_args_list]
    assert len(log_calls) == 8
    assert {
        call.kwargs["extra"]["correlation_id"] for call in log_calls
    } == {result.correlation_id}
