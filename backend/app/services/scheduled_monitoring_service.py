import uuid
import asyncio
from datetime import datetime, timezone
import inspect
from typing import Awaitable, Callable
import time

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.integrations.github.client import GitHubAppClient
from app.models.repository import Repository
from app.monitoring.analyzers import IssueAnalyzer, PullRequestAnalyzer
from app.monitoring.analyzer_base import FindingDraft
from app.monitoring.monitor_service import run_analyzer
from app.services.health_service import compute_and_persist_health
from app.services import finding_service
from app.db.session import SessionLocal

logger = get_logger(__name__)


class CheckResult(BaseModel):
    status: str
    error_message: str | None = None
    checked_at: datetime | None = None


class RepositoryCheckResult(BaseModel):
    correlation_id: str
    status: str
    checks: dict[str, CheckResult] = Field(default_factory=dict)
    reason: str | None = None


class GlobalRunSummary(BaseModel):
    correlation_id: str
    attempted: int = 0
    succeeded: int = 0
    partially_failed: int = 0
    fully_failed: int = 0
    skipped: int = 0
    total_duration: float = 0.0


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

    repository.monitoring_status = "running"
    repository.monitoring_checks = {
        name: {"status": "pending", "error_message": None}
        for name in (
            "stale_issues",
            "stale_prs",
            "dependency",
            "security",
            "code_quality",
            "ci_cd",
            "health",
        )
    }
    db.commit()

    def save_check(name: str, check: CheckResult) -> None:
        check.checked_at = datetime.now(timezone.utc)
        result.checks[name] = check
        checks = dict(repository.monitoring_checks)
        checks[name] = check.model_dump(mode="json")
        repository.monitoring_checks = checks
        db.commit()

    async def run_check(
        name: str, operation: Callable[[], Awaitable[object] | object]
    ) -> None:
        try:
            async def execute() -> object:
                operation_result = operation()
                if inspect.isawaitable(operation_result):
                    return await operation_result
                return operation_result

            operation_result = await asyncio.wait_for(execute(), timeout=25)
            check_status = getattr(operation_result, "status", "success")
            if check_status in {"failed", "skipped", "unavailable"}:
                error_message = getattr(operation_result, "error_message", None)
                result.checks[name] = CheckResult(
                    status=check_status,
                    error_message=error_message or "The check could not be completed.",
                )
                result.status = "partial_failure"
                save_check(name, result.checks[name])
                return
        except Exception:
            result.checks[name] = CheckResult(
                status="failed", error_message="The check could not be completed."
            )
            result.status = "partial_failure"
            save_check(name, result.checks[name])
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
            save_check(name, result.checks[name])
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

    async def scan_ci() -> CheckResult:
        async with GitHubAppClient(
            repository.connection.installation_id
        ) as client:
            runs = await client.list_repository_workflow_runs(
                repository.full_name
            )
        if not runs:
            return CheckResult(
                status="unavailable",
                error_message="GitHub has no workflow-run history to assess.",
            )

        latest_by_workflow: dict[int, dict[str, object]] = {}
        for run in runs:
            if (not isinstance(run, dict) or type(run.get("workflow_id")) is not int
                    or type(run.get("id")) is not int):
                return CheckResult(status="unavailable", error_message="GitHub returned incomplete workflow-run evidence.")
            workflow_id = run.get("workflow_id")
            if isinstance(workflow_id, int):
                latest_by_workflow.setdefault(workflow_id, run)
        if not latest_by_workflow or any(
            run.get("status") != "completed" or run.get("conclusion") not in {
                "success", "failure", "timed_out", "cancelled", "neutral", "skipped", "action_required", "stale", "startup_failure"
            }
            for run in latest_by_workflow.values()
        ):
            return CheckResult(
                status="unavailable",
                error_message="The latest workflow runs are not all complete.",
            )

        drafts: list[FindingDraft] = []
        for run in latest_by_workflow.values():
            conclusion = run.get("conclusion")
            if conclusion in {"success", "neutral", "skipped"}:
                continue
            run_id = run.get("id")
            name = str(run.get("name") or "GitHub Actions")
            drafts.append(
                FindingDraft(
                    category="ci",
                    type_=f"workflow_run_{conclusion}",
                    title=f"Workflow '{name}' {conclusion}",
                    description=(
                        f"The latest run of workflow '{name}' completed with "
                        f"conclusion '{conclusion}'."
                    ),
                    severity="low" if conclusion == "cancelled" else "high",
                    evidence={
                        "workflow_name": name,
                        "run_id": run_id,
                        "workflow_id": run["workflow_id"],
                        "conclusion": conclusion,
                        "url": run.get("html_url"),
                    },
                    fingerprint=f"ci:{repository.id}:workflow_run:{run_id}",
                )
            )
        finding_service.sync_findings_for_run(
            db,
            repository_id=repository.id,
            category="ci",
            analyzer_key="ci",
            drafts=drafts,
        )
        return CheckResult(status="success")

    async def run_named_analyzer(name: str) -> object:
        # Persist a single snapshot after all current-run category checks finish.
        return await run_analyzer(db, name, repository, recompute_health=False)

    async def recalculate_health() -> CheckResult:
        snapshot = compute_and_persist_health(db, repository.id)
        if snapshot is None:
            return CheckResult(
                status="unavailable",
                error_message="No category was successfully assessed; a current health score is unavailable.",
            )
        return CheckResult(status="success")

    checks = (
        ("stale_issues", scan_stale_issues),
        ("stale_prs", scan_stale_prs),
        ("dependency", lambda: run_named_analyzer("dependency")),
        ("security", lambda: run_named_analyzer("security")),
        ("code_quality", lambda: run_named_analyzer("code_quality")),
        ("ci_cd", scan_ci),
        ("health", recalculate_health),
    )
    for name, operation in checks:
        db.refresh(repository)
        if not repository.monitoring_enabled:
            repository.monitoring_status = "disabled"
            db.commit()
            result.status = "skipped"
            result.reason = "monitoring_disabled"
            return result
        await run_check(name, operation)

    completed_checks = list(result.checks.values())
    if completed_checks and all(
        check.status == "failed" for check in completed_checks
    ):
        result.status = "failed"
    elif any(check.status != "success" for check in completed_checks):
        result.status = "partial_failure"
    else:
        result.status = "success"

    logger.info(
        "Finished scheduled monitoring checks",
        extra={
            "repository_id": str(repository.id),
            "correlation_id": correlation_id,
            "status": result.status,
        },
    )
    db.refresh(repository)
    if not repository.monitoring_enabled:
        repository.monitoring_status = "disabled"
        result.status = "skipped"
        result.reason = "monitoring_disabled"
    else:
        repository.monitoring_status = result.status
    repository.last_monitoring_at = datetime.now(timezone.utc)
    db.commit()
    return result


def run_initial_assessment_in_background(repository_id: str) -> None:
    """Run the queued initial assessment with an isolated database session."""
    db = SessionLocal()
    try:
        # Claim persisted work atomically: startup recovery and the enabling
        # request (or multiple API workers) can discover the same queued row.
        claimed = db.query(Repository).filter(
            Repository.id == uuid.UUID(repository_id),
            Repository.monitoring_enabled.is_(True),
            Repository.monitoring_status == "queued",
        ).update({Repository.monitoring_status: "running"}, synchronize_session=False)
        db.commit()
        if not claimed:
            return
        repository = db.query(Repository).filter(
            Repository.id == uuid.UUID(repository_id)
        ).first()
        if repository is None or not repository.monitoring_enabled:
            return
        try:
            asyncio.run(run_monitoring_checks_for_repository(db, repository))
        except Exception:
            logger.error(
                "Initial repository assessment failed unexpectedly",
                exc_info=True,
                extra={"repository_id": repository_id},
            )
            db.rollback()
            repository = db.query(Repository).filter(
                Repository.id == uuid.UUID(repository_id)
            ).first()
            if repository is not None and repository.monitoring_enabled:
                checks = dict(repository.monitoring_checks)
                checks["assessment"] = {
                    "status": "failed",
                    "error_message": "The assessment could not be completed.",
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
                repository.monitoring_checks = checks
                repository.monitoring_status = "failed"
                repository.last_monitoring_at = datetime.now(timezone.utc)
                db.commit()
            raise
    finally:
        db.close()


def resume_queued_initial_assessments() -> None:
    """Resume persisted queued work, including migration backfills, on startup."""
    try:
        with SessionLocal() as db:
            repository_ids = [str(row.id) for row in db.query(Repository.id).filter(
                Repository.monitoring_enabled.is_(True),
                Repository.monitoring_status == "queued",
            ).all()]
    except Exception:
        logger.error("Could not load queued initial assessments", exc_info=True)
        return
    for repository_id in repository_ids:
        try:
            run_initial_assessment_in_background(repository_id)
        except Exception:
            # The runner records terminal failure; one failure must not strand
            # the rest of the queue. No AI provider is involved in this path.
            logger.error("Could not resume queued assessment",
                         extra={"repository_id": repository_id}, exc_info=True)


async def run_scheduled_monitoring_cycle(db: Session) -> GlobalRunSummary:
    correlation_id = str(uuid.uuid4())
    logger.info(
        "Starting global scheduled monitoring cycle",
        extra={"correlation_id": correlation_id}
    )
    
    start_time = time.perf_counter()
    summary = GlobalRunSummary(correlation_id=correlation_id)
    
    # Query all repositories with monitoring_enabled = True
    repositories = db.query(Repository).filter(Repository.monitoring_enabled == True).all()
    
    for repo in repositories:
        summary.attempted += 1
        try:
            repo_result = await run_monitoring_checks_for_repository(db, repo)
            if repo_result.status == "success":
                summary.succeeded += 1
            elif repo_result.status == "partial_failure":
                summary.partially_failed += 1
            elif repo_result.status == "failed":
                summary.fully_failed += 1
            elif repo_result.status == "skipped":
                summary.skipped += 1
            else:
                # Should not happen ideally, but count as failed or unknown
                summary.fully_failed += 1
        except Exception as exc:
            summary.fully_failed += 1
            logger.error(
                "Repository monitoring completely failed during global cycle",
                exc_info=True,
                extra={
                    "repository_id": str(repo.id),
                    "correlation_id": correlation_id
                }
            )
            
    summary.total_duration = time.perf_counter() - start_time
    
    logger.info(
        "Finished global scheduled monitoring cycle",
        extra={
            "correlation_id": correlation_id,
            "attempted": summary.attempted,
            "succeeded": summary.succeeded,
            "partially_failed": summary.partially_failed,
            "fully_failed": summary.fully_failed,
            "skipped": summary.skipped,
            "duration": summary.total_duration,
        }
    )
    return summary
