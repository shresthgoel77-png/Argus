import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.schemas.health import HealthSnapshotResponse, HealthSnapshotListResponse
from app.services.repository_service import get_repository_or_404
from app.services import health_service
from app.models.repository_health_snapshot import RepositoryHealthSnapshot

router = APIRouter(prefix="/repositories/{repository_id}", tags=["health"])

def _with_previous_score(db: Session, snapshot: RepositoryHealthSnapshot) -> RepositoryHealthSnapshot:
    """Helper to attach previous_score dynamically for Pydantic validation."""
    previous = (
        db.query(RepositoryHealthSnapshot)
        .filter(
            RepositoryHealthSnapshot.repository_id == snapshot.repository_id,
            RepositoryHealthSnapshot.id != snapshot.id,
            RepositoryHealthSnapshot.computed_at <= snapshot.computed_at
        )
        .order_by(desc(RepositoryHealthSnapshot.computed_at))
        .first()
    )
    setattr(snapshot, "previous_score", previous.overall_score if previous else None)
    return snapshot


@router.get("/health", response_model=HealthSnapshotResponse)
def get_repository_health(
    repository_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns latest snapshot with previous_score.
    Lazily computes first snapshot if none exists.
    """
    get_repository_or_404(db=db, user_id=user.id, repository_id=repository_id)
    
    latest = health_service.get_latest_snapshot(db, repository_id)
    if not latest:
        latest = health_service.compute_and_persist_health(db, repository_id)
        
    latest = _with_previous_score(db, latest)
    return HealthSnapshotResponse.model_validate(latest)


@router.get("/health/history", response_model=HealthSnapshotListResponse)
def get_repository_health_history(
    repository_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100000),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns paginated history of health snapshots.
    """
    get_repository_or_404(db=db, user_id=user.id, repository_id=repository_id)
    
    query = (
        db.query(RepositoryHealthSnapshot)
        .filter(RepositoryHealthSnapshot.repository_id == repository_id)
        .order_by(desc(RepositoryHealthSnapshot.computed_at))
    )
    total = query.count()
    items = query.limit(limit).offset(offset).all()
    
    for item in items:
        _with_previous_score(db, item)
        
    return HealthSnapshotListResponse(
        items=[HealthSnapshotResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset
    )


@router.post("/health-runs", response_model=HealthSnapshotResponse)
def create_repository_health_run(
    repository_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Synchronously triggers compute_and_persist_health and returns new snapshot.
    """
    get_repository_or_404(db=db, user_id=user.id, repository_id=repository_id)
    
    new_snapshot = health_service.compute_and_persist_health(db, repository_id)
    new_snapshot = _with_previous_score(db, new_snapshot)
    
    return HealthSnapshotResponse.model_validate(new_snapshot)
