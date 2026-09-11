import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.schemas.repository import RepositoryRead, RepositoryCreate, RepositoryUpdate
from app.services.github_connection_service import get_connection_or_404
from app.services.repository_service import (
    add_repository,
    list_repositories_for_user,
    set_monitoring_enabled
)
from app.integrations.github.client import GitHubAppClient

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
    connection = get_connection_or_404(db=db, user_id=user.id, connection_id=repo_in.connection_id)
    client = GitHubAppClient()
    return await add_repository(db=db, connection=connection, github_repo_id=repo_in.github_repo_id, client=client)

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
