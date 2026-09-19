import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
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
