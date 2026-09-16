import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.schemas.finding import (
    FindingResponse,
    FindingListResponse,
    FindingStatusUpdateRequest,
)
from app.services.finding_service import list_findings, get_finding_or_404
from app.services import finding_lifecycle_service
from app.services.finding_lifecycle_service import InvalidFindingTransition
from app.services import ai_analysis_service
from app.schemas.ai_analysis import (
    AIAnalysisResponse,
    AIAnalysisHistoryResponse,
    AIAnalysisNotExists,
)


router = APIRouter(prefix="/findings", tags=["findings"])

@router.get("", response_model=FindingListResponse)
def get_user_findings(
    repository_id: uuid.UUID | None = None,
    category: str | None = None,
    severity: str | None = None,
    priority: str | None = None,
    status_: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List findings across all repositories the current user owns."""
    total, items = list_findings(
        db=db,
        user_id=user.id,
        repository_id=repository_id,
        category=category,
        severity=severity,
        priority=priority,
        status=status_,
        limit=limit,
        offset=offset
    )
    return FindingListResponse(
        items=[FindingResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/{finding_id}", response_model=FindingResponse)
def get_finding(
    finding_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a single finding by ID, ensuring ownership."""
    return get_finding_or_404(db=db, user_id=user.id, finding_id=finding_id)


@router.patch("/{finding_id}", response_model=FindingResponse)
def update_finding_status(
    finding_id: uuid.UUID,
    update_req: FindingStatusUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update finding status.
    Dispatches to the appropriate finding_lifecycle_service function.
    Returns 409 Conflict if the transition is invalid.
    """
    finding = get_finding_or_404(db=db, user_id=user.id, finding_id=finding_id)

    try:
        if update_req.status == "acknowledged":
            finding_lifecycle_service.acknowledge_finding(db, finding)
        elif update_req.status == "resolved":
            finding_lifecycle_service.resolve_finding(
                db, finding, source="manual"
            )
        elif update_req.status == "ignored":
            finding_lifecycle_service.ignore_finding(db, finding)
        elif update_req.status == "open":
            finding_lifecycle_service.reopen_finding(db, finding)
    except InvalidFindingTransition as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    return finding


@router.post("/{finding_id}/ai-analysis", response_model=AIAnalysisResponse)
def create_finding_ai_analysis(
    finding_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Triggers a new AI analysis for the finding synchronously.
    Returns the resulting AIAnalysis (whether completed or failed).
    """
    finding = get_finding_or_404(db=db, user_id=user.id, finding_id=finding_id)
    
    try:
        analysis = ai_analysis_service.request_finding_analysis(finding=finding, user=user)
        return AIAnalysisResponse.model_validate(analysis)
    except ai_analysis_service.AINotConfiguredError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid AI connection is configured. Please complete setup in the Settings AI/BYOK section."
        ) from e
    except ai_analysis_service.AIAnalysisFailedError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=e.message
        ) from e


@router.get(
    "/{finding_id}/ai-analysis", 
    response_model=AIAnalysisResponse | AIAnalysisNotExists
)
def get_latest_finding_ai_analysis(
    finding_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns the latest AIAnalysis for the finding, or {exists: false} if none exists.
    """
    finding = get_finding_or_404(db=db, user_id=user.id, finding_id=finding_id)
    latest = ai_analysis_service.get_latest_analysis(finding=finding)
    
    if not latest:
        return AIAnalysisNotExists()
    return AIAnalysisResponse.model_validate(latest)


@router.get("/{finding_id}/ai-analysis/history", response_model=AIAnalysisHistoryResponse)
def get_finding_ai_analysis_history(
    finding_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns a paginated list of all prior AI analyses for the finding, newest first.
    """
    finding = get_finding_or_404(db=db, user_id=user.id, finding_id=finding_id)
    total, items = ai_analysis_service.list_analyses(
        finding=finding,
        limit=limit,
        offset=offset
    )
    
    return AIAnalysisHistoryResponse(
        items=[AIAnalysisResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset
    )
