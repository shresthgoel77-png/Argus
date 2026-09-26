import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas.scheduled_monitoring import ScheduledMonitoringRunSummary
from app.services.scheduled_monitoring_service import (
    run_scheduled_monitoring_cycle,
)


router = APIRouter(
    prefix="/internal",
    include_in_schema=False,
)


def require_scheduler_secret(
    scheduler_secret: str | None = Header(
        default=None,
        alias="X-Scheduler-Secret",
    ),
) -> None:
    """Authenticate the trusted scheduler without creating a user identity.

    This is an intentionally isolated exception to the user-facing Auth
    abstraction: the caller is a trusted machine and has no user context.
    """
    configured_secret = settings.scheduler_shared_secret
    configured_value = (
        configured_secret.get_secret_value() if configured_secret else ""
    )
    supplied_value = scheduler_secret or ""
    if not configured_value or not secrets.compare_digest(
        supplied_value.encode("utf-8"),
        configured_value.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )


@router.post(
    "/scheduled-monitoring/run",
    response_model=ScheduledMonitoringRunSummary,
    dependencies=[Depends(require_scheduler_secret)],
)
async def run_scheduled_monitoring(
    db: Session = Depends(get_db),
) -> ScheduledMonitoringRunSummary:
    summary = await run_scheduled_monitoring_cycle(db)
    return ScheduledMonitoringRunSummary.model_validate(summary.model_dump())
