import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.db.session import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.ai_analysis import AIAnalysis
from app.schemas.repository import (
    RepositoryRead,
    RepositoryCreate,
    RepositoryUpdate,
)
from app.services.github_connection_service import get_connection_or_404
from app.services.repository_service import (
    add_repository,
    list_repositories_for_user,
    set_monitoring_enabled,
    get_repository_or_404
)
from app.integrations.github.client import GitHubAppClient
from app.schemas.finding import FindingListResponse, FindingResponse
from app.services.finding_service import list_findings
from app.schemas.activity import ActivityFeedResponse, ActivitySource
from app.services.activity_feed_service import get_activity_feed
from app.schemas.ai_analysis import (
    AIAnalysisResponse,
    AIAnalysisHistoryResponse,
    AIAnalysisNotExists,
)
from app.services.ai_analysis_service import (
    request_repository_summary,
    AINotConfiguredError,
    AIAnalysisFailedError,
)
from app.schemas.trend import (
    TrendResponse,
    HealthTrend,
    CategoryDelta,
    FindingVelocity,
    CategoryVelocity,
)
from app.services.trend_service import get_health_trend, get_finding_velocity
from app.schemas.dashboard_overview import DashboardOverviewResponse
from app.services.health_service import get_latest_snapshot
from app.services.needs_attention_service import get_needs_attention
from app.services.finding_service import get_all_open_findings_for_repository

router = APIRouter(prefix="/repositories", tags=["repositories"])

@router.post("", response_model=RepositoryRead)
async def create_repository(
    repo_in: RepositoryCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Subscribes (adds) a repository for monitoring.
    Verifies that the provided connection is owned by the current user.
    """
    connection = get_connection_or_404(
        db=db, user_id=user.id, connection_id=repo_in.connection_id
    )
    client = GitHubAppClient(installation_id=connection.installation_id)
    return await add_repository(
        db=db,
        connection=connection,
        github_repo_id=repo_in.github_repo_id,
        client=client
    )

@router.get("", response_model=list[RepositoryRead])
def get_user_repositories(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns the list of persisted repositories that the user has added.
    """
    return list_repositories_for_user(db=db, user_id=user.id)


@router.patch("/{repository_id}", response_model=RepositoryRead)
def update_repository(
    repository_id: uuid.UUID,
    repo_in: RepositoryUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Toggles monitoring enabled status for a repository.
    Verifies ownership before updating.
    """
    return set_monitoring_enabled(
        db=db,
        user_id=user.id,
        repository_id=repository_id,
        enabled=repo_in.monitoring_enabled
    )

@router.get("/{repository_id}/findings", response_model=FindingListResponse)
def get_repository_findings(
    repository_id: uuid.UUID,
    category: str | None = None,
    severity: str | None = None,
    priority: str | None = None,
    status_: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns findings scoped to a single repository owned by the user.
    """
    # 1. Enforce ownership and existence
    get_repository_or_404(db=db, user_id=user.id, repository_id=repository_id)

    # 2. Re-use list_findings with the repository_id filter
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


@router.get("/{repository_id}/activity", response_model=ActivityFeedResponse)
def get_repository_activity(
    repository_id: uuid.UUID,
    before: datetime | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    source: ActivitySource | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_repository_or_404(db=db, user_id=user.id, repository_id=repository_id)
    items, next_before = get_activity_feed(db=db, repository_id=repository_id, before=before, limit=limit, source=source)
    return ActivityFeedResponse(items=items, next_before=next_before)


@router.post("/{repository_id}/ai-summary", response_model=AIAnalysisResponse)
def create_repository_ai_summary(
    repository_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Triggers a new AI summary for the repository synchronously.
    """
    get_repository_or_404(db=db, user_id=user.id, repository_id=repository_id)

    try:
        analysis = request_repository_summary(db=db, repository_id=repository_id, user=user)
        return AIAnalysisResponse.model_validate(analysis)
    except AINotConfiguredError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid AI connection is configured. Please complete setup in the Settings AI/BYOK section."
        ) from e
    except AIAnalysisFailedError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=e.message
        ) from e


def get_latest_repo_analysis(db: Session, repository_id: uuid.UUID) -> AIAnalysis | None:
    return (
        db.query(AIAnalysis)
        .filter(
            AIAnalysis.repository_id == repository_id,
            AIAnalysis.analysis_type == "repository_summary"
        )
        .order_by(desc(AIAnalysis.requested_at))
        .first()
    )

def list_repo_analyses(db: Session, repository_id: uuid.UUID, limit: int, offset: int) -> tuple[int, list[AIAnalysis]]:
    query = (
        db.query(AIAnalysis)
        .filter(
            AIAnalysis.repository_id == repository_id,
            AIAnalysis.analysis_type == "repository_summary"
        )
    )
    total = query.count()
    items = (
        query.order_by(desc(AIAnalysis.requested_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return total, items


@router.get(
    "/{repository_id}/ai-summary", 
    response_model=AIAnalysisResponse | AIAnalysisNotExists
)
def get_latest_repository_ai_summary(
    repository_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns the latest AIAnalysis (type: repository_summary) for the repository, or {exists: false} if none exists.
    """
    get_repository_or_404(db=db, user_id=user.id, repository_id=repository_id)

    latest = get_latest_repo_analysis(db, repository_id)

    if not latest:
        return AIAnalysisNotExists()
    return AIAnalysisResponse.model_validate(latest)


@router.get("/{repository_id}/ai-summary/history", response_model=AIAnalysisHistoryResponse)
def get_repository_ai_summary_history(
    repository_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns a paginated list of all prior AI analyses for the repository, newest first.
    """
    get_repository_or_404(db=db, user_id=user.id, repository_id=repository_id)

    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)

    total, items = list_repo_analyses(db, repository_id, limit, offset)

    return AIAnalysisHistoryResponse(
        items=[AIAnalysisResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/{repository_id}/trends", response_model=TrendResponse)
def get_repository_trends(
    repository_id: uuid.UUID,
    window_days: int = Query(default=30, ge=1, le=90),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns repository health trends and finding velocity analytics in a given window.
    """
    get_repository_or_404(db=db, user_id=user.id, repository_id=repository_id)

    overall_delta, category_deltas_dict = get_health_trend(db, repository_id, window_days)
    velocity_dict = get_finding_velocity(db, repository_id, window_days)

    health_trend = HealthTrend(
        overall_delta=overall_delta,
        category_deltas=[
            CategoryDelta(category=k, delta=v)
            for k, v in category_deltas_dict.items()
        ]
    )

    finding_velocity = FindingVelocity(
        categories=[
            CategoryVelocity(category=k, detected=v["detected"], resolved=v["resolved"])
            for k, v in velocity_dict.items()
        ]
    )

    return TrendResponse(
        window_days=window_days,
        health_trend=health_trend,
        finding_velocity=finding_velocity
    )


@router.get("/{repository_id}/dashboard", response_model=DashboardOverviewResponse)
def get_dashboard_overview(
    repository_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Composed dashboard overview endpoint that reads from multiple domains without triggering new AI analysis.
    """
    get_repository_or_404(db=db, user_id=user.id, repository_id=repository_id)

    # 1. Health
    health_snapshot = get_latest_snapshot(db, repository_id)

    # 2. Needs Attention (uses open findings inside)
    # The return type of get_needs_attention is NeedsAttentionDTO
    # Which maps easily to our NeedsAttentionResponse schema via from_attributes=True mapping, because Finding mapped to FindingResponse
    needs_attention_dto = get_needs_attention(db, repository_id, limit=5)

    # 3. Activity feed
    activity_items, _ = get_activity_feed(db=db, repository_id=repository_id, limit=5)

    # 4. AI Summary (latest, do not trigger generation)
    latest_ai_summary = get_latest_repo_analysis(db, repository_id)

    # 5. Trends (default 30 days window)
    overall_delta, category_deltas_dict = get_health_trend(db, repository_id, window_days=30)
    velocity_dict = get_finding_velocity(db, repository_id, window_days=30)

    health_trend = HealthTrend(
        overall_delta=overall_delta,
        category_deltas=[
            CategoryDelta(category=k, delta=v)
            for k, v in category_deltas_dict.items()
        ]
    )

    finding_velocity = FindingVelocity(
        categories=[
            CategoryVelocity(category=k, detected=v["detected"], resolved=v["resolved"])
            for k, v in velocity_dict.items()
        ]
    )

    trends = TrendResponse(
        window_days=30,
        health_trend=health_trend,
        finding_velocity=finding_velocity
    )

    # 6. Open finding counts by category
    open_findings = get_all_open_findings_for_repository(db, repository_id)
    finding_counts = {
        "ci_cd": 0,
        "dependencies": 0,
        "security": 0,
        "issues": 0,
        "pull_requests": 0,
        "code_quality": 0,
    }
    # Using predefined valid categories from instructions/other parts
    for finding in open_findings:
        if finding.category in finding_counts:
            finding_counts[finding.category] += 1
        else:
            finding_counts[finding.category] = 1 # Just in case a category differs

    # Assemble composed response
    return DashboardOverviewResponse(
        repository_id=repository_id,
        health=health_snapshot,
        needs_attention=needs_attention_dto,
        activity_feed=activity_items,
        ai_summary=latest_ai_summary if latest_ai_summary else AIAnalysisNotExists(),
        trends=trends,
        finding_category_counts=finding_counts
    )

