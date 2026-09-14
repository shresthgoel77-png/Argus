import pytest
from app.models.repository_health_snapshot import RepositoryHealthSnapshot
from app.models.repository import Repository

def test_repository_health_snapshot_creation(db_session, test_user_repository: Repository):
    snapshot = RepositoryHealthSnapshot(
        repository_id=test_user_repository.id,
        overall_score=85,
        category_scores={"security": 90, "maintenance": 80}
    )
    
    db_session.add(snapshot)
    db_session.commit()
    db_session.refresh(snapshot)
    
    assert snapshot.id is not None, "Expected ID to be populated by default UUID generator"
    assert snapshot.repository_id == test_user_repository.id, "Expected matching foreign key for repository"
    assert snapshot.overall_score == 85, "Expected overall score to match" 
    assert snapshot.reasons == [], "Expected reasons to default to empty list []"
    assert snapshot.computed_at is not None, "Expected computed_at to be populated by server default func.now()"
    
    res = db_session.query(RepositoryHealthSnapshot).order_by(RepositoryHealthSnapshot.computed_at.desc()).first()
    assert res.id == snapshot.id
