import pytest
from httpx import AsyncClient
import uuid
from app.models.repository import Repository
from app.models.repository_health_snapshot import RepositoryHealthSnapshot
from app.models.finding import Finding
from app.db.session import get_db

@pytest.mark.asyncio
async def test_repo_health_api_unauthenticated(async_client: AsyncClient, test_user_repository: Repository):
    response = await async_client.get(
        f"/api/v1/repositories/{test_user_repository.id}/health"
    )
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_repo_health_api_not_found_or_unowned(authorized_client: AsyncClient):
    fake_id = str(uuid.uuid4())
    response = await authorized_client.get(
        f"/api/v1/repositories/{fake_id}/health"
    )
    assert response.status_code == 404

    response = await authorized_client.post(
        f"/api/v1/repositories/{fake_id}/health-runs"
    )
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_repo_health_lazy_compute_and_post(db_session, authorized_client: AsyncClient, test_user_repository: Repository):
    # Ensure no snapshots exist
    count = db_session.query(RepositoryHealthSnapshot).filter(RepositoryHealthSnapshot.repository_id == test_user_repository.id).count()
    assert count == 0
    
    # Add a mock finding for the respository so we have something to score
    finding = Finding(
        id=uuid.uuid4(),
        repository_id=test_user_repository.id,
        category="security",
        type="test_sec",
        title="Sec Finding",
        description="test",
        severity="high",
        status="open",
        source="cli",
        evidence={},
    )
    db_session.add(finding)
    db_session.commit()

    # Access health endpoint - should lazily compute
    response = await authorized_client.get(
        f"/api/v1/repositories/{test_user_repository.id}/health"
    )
    assert response.status_code == 200
    data = response.json()
    assert "overall_score" in data
    assert data["previous_score"] is None
    
    # Trigger a health run via POST
    response2 = await authorized_client.post(
        f"/api/v1/repositories/{test_user_repository.id}/health-runs"
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert "overall_score" in data2
    assert data2["previous_score"] == data["overall_score"]
    
    # Ensure we now have 2 snapshots
    assert db_session.query(RepositoryHealthSnapshot).filter(RepositoryHealthSnapshot.repository_id == test_user_repository.id).count() == 2

@pytest.mark.asyncio
async def test_repo_health_history_pagination(db_session, authorized_client: AsyncClient, test_user_repository: Repository):
    # Ensure no snapshots exist
    db_session.query(RepositoryHealthSnapshot).filter(RepositoryHealthSnapshot.repository_id == test_user_repository.id).delete()
    db_session.commit()
    
    # Trigger 3 health runs
    for _ in range(3):
        await authorized_client.post(f"/api/v1/repositories/{test_user_repository.id}/health-runs")
        
    response = await authorized_client.get(
        f"/api/v1/repositories/{test_user_repository.id}/health/history?limit=2&offset=0"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0
    
    # Second page
    response = await authorized_client.get(
        f"/api/v1/repositories/{test_user_repository.id}/health/history?limit=2&offset=2"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
