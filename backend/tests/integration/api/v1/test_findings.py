from uuid import uuid4
import pytest
from app.models.finding import Finding

@pytest.fixture
def test_finding(db_session, test_user_repository):
    finding = Finding(
        repository_id=test_user_repository.id,
        category="security",
        type="secret_leak",
        title="Hardcoded API Key",
        description="Key found in config.",
        severity="high",
        status="open",
        source="scanner",
        evidence={"line": 42},
        priority="P1",
        fingerprint="test1234"
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)
    return finding

@pytest.fixture
def other_user_repository(db_session):
    import uuid
    from app.models.user import User
    from app.models.github_connection import GitHubConnection
    from app.models.repository import Repository
    
    other_user = User(email="other@example.com", auth_provider="test")
    db_session.add(other_user)
    db_session.commit()
    
    conn = GitHubConnection(user_id=other_user.id, installation_id=999, account_login="other", account_type="User", status="active")
    db_session.add(conn)
    db_session.commit()
    
    repo = Repository(connection_id=conn.id, github_repo_id=999, full_name="other/repo", monitoring_enabled=True)
    db_session.add(repo)
    db_session.commit()
    
    return repo

@pytest.fixture
def other_user_finding(db_session, other_user_repository):
    finding = Finding(
        repository_id=other_user_repository.id,
        category="security",
        type="secret_leak",
        title="Other Hardcoded API Key",
        description="Key found in config.",
        severity="high",
        status="open",
        source="scanner",
        evidence={"line": 99},
        priority="P1",
        fingerprint="test999"
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)
    return finding


@pytest.mark.asyncio
async def test_get_findings_list(authorized_client, test_finding):
    response = await authorized_client.get("/api/v1/findings")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == str(test_finding.id)
    assert "fingerprint" not in data["items"][0]

@pytest.mark.asyncio
async def test_get_findings_list_filters(authorized_client, test_finding):
    response = await authorized_client.get(f"/api/v1/findings?status_=open&category=security&repository_id={test_finding.repository_id}")
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    
    response = await authorized_client.get("/api/v1/findings?status_=resolved")
    assert len(response.json()["items"]) == 0

@pytest.mark.asyncio
async def test_get_repository_findings(authorized_client, test_user_repository, test_finding):
    response = await authorized_client.get(f"/api/v1/repositories/{test_user_repository.id}/findings")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == str(test_finding.id)

@pytest.mark.asyncio
async def test_get_repository_findings_unowned(authorized_client, other_user_repository):
    response = await authorized_client.get(f"/api/v1/repositories/{other_user_repository.id}/findings")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_get_finding_detail(authorized_client, test_finding):
    response = await authorized_client.get(f"/api/v1/findings/{test_finding.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(test_finding.id)
    assert "fingerprint" not in data

@pytest.mark.asyncio
async def test_get_finding_detail_unowned(authorized_client, other_user_finding):
    response = await authorized_client.get(f"/api/v1/findings/{other_user_finding.id}")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_patch_finding_status(authorized_client, test_finding, db_session):
    response = await authorized_client.patch(
        f"/api/v1/findings/{test_finding.id}",
        json={"status": "acknowledged"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "acknowledged"
    
    # Verify in DB
    db_session.refresh(test_finding)
    assert test_finding.status == "acknowledged"
    assert test_finding.acknowledged_at is not None

@pytest.mark.asyncio
async def test_patch_finding_status_conflict(authorized_client, test_finding):
    # Transition open -> resolved is valid. resolved -> ignored is conflict.
    resp1 = await authorized_client.patch(f"/api/v1/findings/{test_finding.id}", json={"status": "resolved"})
    assert resp1.status_code == 200
    
    resp2 = await authorized_client.patch(f"/api/v1/findings/{test_finding.id}", json={"status": "ignored"})
    assert resp2.status_code == 409

@pytest.mark.asyncio
async def test_patch_finding_unowned(authorized_client, other_user_finding):
    response = await authorized_client.patch(f"/api/v1/findings/{other_user_finding.id}", json={"status": "acknowledged"})
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_unauthenticated(async_client, test_finding, test_user_repository):
    resp1 = await async_client.get("/api/v1/findings")
    assert resp1.status_code == 401
    
    resp2 = await async_client.get(f"/api/v1/repositories/{test_user_repository.id}/findings")
    assert resp2.status_code == 401
    
    resp3 = await async_client.get(f"/api/v1/findings/{test_finding.id}")
    assert resp3.status_code == 401
    
    resp4 = await async_client.patch(f"/api/v1/findings/{test_finding.id}", json={"status": "resolved"})
    assert resp4.status_code == 401
    
