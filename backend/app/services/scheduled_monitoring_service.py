import uuid
import inspect
from typing import Awaitable, Callable

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.integrations.github.client import GitHubAppClient
from app.models.repository import Repository
from app.monitoring.analyzers import IssueAnalyzer, PullRequestAnalyzer
from app.monitoring.monitor_service import run_analyzer
from app.services.health_service import compute_and_persist_health

logger = get_logger(__name__)


class CheckResult(BaseModel):
    status: str
    error_message: str | None = None


class RepositoryCheckResult(BaseModel):
    correlation_id: str
    status: str
    checks: dict[str, CheckResult] = Field(default_factory=dict)
    reason: str | None = None


async def run_monitoring_checks_for_repository(
    db: Session, repository: Repository
) -> RepositoryCheckResult:
    correlation_id = str(uuid.uuid4())
    result = RepositoryCheckResult(
        correlation_id=correlation_id,
        status="success",
    )

    logger.info(
        "Starting scheduled monitoring checks",
        extra={
            "repository_id": str(repository.id),
            "correlation_id": correlation_id,
        },
    )

    if not repository.monitoring_enabled:
        result.status = "skipped"
        result.reason = "monitoring_disabled"
        logger.info(
            "Scheduled monitoring checks skipped",
            extra={
                "repository_id": str(repository.id),
                "correlation_id": correlation_id,
                "reason": result.reason,
            },
        )
        return result

    async def run_check(
        name: str, operation: Callable[[], Awaitable[object] | object]
    ) -> None:
        try:
            operation_result = operation()
            if inspect.isawaitable(operation_result):
                operation_result = await operation_result
            if (
                getattr(operation_result, "status", "success") == "failed"
            ):
                error_message = getattr(
                    operation_result, "error_message", None
                )
                raise RuntimeError(
                    error_message or "Check reported failure"
                )
        except Exception as exc:
            result.checks[name] = CheckResult(
                status="failed", error_message=str(exc)
            )
            result.status = "partial_failure"
            logger.error(
                "Scheduled monitoring check failed",
                exc_info=True,
                extra={
                    "repository_id": str(repository.id),
                    "check": name,
                    "correlation_id": correlation_id,
                },
            )
        else:
            result.checks[name] = CheckResult(status="success")
            logger.info(
                "Scheduled monitoring check completed",
                extra={
                    "repository_id": str(repository.id),
                    "check": name,
                    "correlation_id": correlation_id,
                },
            )

    async def scan_stale_issues() -> None:
        async with GitHubAppClient(
            repository.connection.installation_id
        ) as client:
            await IssueAnalyzer().scan_repository_for_stale_issues(
                db, repository, client
            )

    async def scan_stale_prs() -> None:
        async with GitHubAppClient(
            repository.connection.installation_id
        ) as client:
            await PullRequestAnalyzer().scan_repository_for_stale_prs(
                db, repository, client
            )

    async def run_named_analyzer(name: str) -> object:
        return await run_analyzer(db, name, repository)

    async def recalculate_health() -> None:
        compute_and_persist_health(db, repository.id)

    checks = (
        ("stale_issues", scan_stale_issues),
        ("stale_prs", scan_stale_prs),
        ("dependency", lambda: run_named_analyzer("dependency")),
        ("security", lambda: run_named_analyzer("security")),
        ("code_quality", lambda: run_named_analyzer("code_quality")),
        ("health", recalculate_health),
    )
    for name, operation in checks:
        await run_check(name, operation)

    logger.info(
        "Finished scheduled monitoring checks",
        extra={
            "repository_id": str(repository.id),
            "correlation_id": correlation_id,
            "status": result.status,
        },
    )
    return result
