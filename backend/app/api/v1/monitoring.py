import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.schemas.monitoring import MonitorRunRequest, MonitorRunResult
from app.services.repository_service import get_repository_or_404
from app.monitoring.monitor_service import run_analyzer

router = APIRouter(prefix="/repositories/{repository_id}/monitor-runs", tags=["monitoring"])

@router.post("", response_model=MonitorRunResult)
async def create_monitor_run(
    repository_id: uuid.UUID,
    request: MonitorRunRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    On-demand trigger for an analyzer run.
    Ensures repository belongs to the user, and skips execution if monitoring is disabled.
    """
    repository = get_repository_or_404(db=db, user_id=user.id, repository_id=repository_id)
    result = await run_analyzer(db=db, analyzer_key=request.analyzer_key, repository=repository)
    return result
