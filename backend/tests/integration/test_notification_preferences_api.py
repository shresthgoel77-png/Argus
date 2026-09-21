import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.models.notification_preference import NotificationSeverity
from app.models.user import User

@pytest.mark.asyncio
async def test_get_preferences_auto_creates(authorized_client, test_user):
    response = await authorized_client.get("/api/v1/notifications/preferences")
    assert response.status_code == 200
    data = response.json()
    assert data["email_enabled"] is False
    assert data["min_severity_email"] == NotificationSeverity.high.value
    assert data["user_id"] == str(test_user.id)
    assert "id" in data

@pytest.mark.asyncio
async def test_update_preferences(authorized_client):
    response = await authorized_client.put(
        "/api/v1/notifications/preferences",
        json={
            "email_enabled": True,
            "min_severity_email": "critical"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email_enabled"] is True
    assert data["min_severity_email"] == "critical"

    # Verify update persisted
    get_response = await authorized_client.get("/api/v1/notifications/preferences")
    assert get_response.json()["email_enabled"] is True
    assert get_response.json()["min_severity_email"] == "critical"

@pytest.mark.asyncio
async def test_auth_scoping_isolation(authorized_client, db_session, test_user):
    # Set preference for test_user
    await authorized_client.put("/api/v1/notifications/preferences", json={"email_enabled": True})
    
    # Create a second user
    u2 = User(
        email=f"test2_{uuid.uuid4()}@example.com",
        display_name="Test User 2",
        auth_provider="development",
        external_auth_id=str(uuid.uuid4())
    )
    db_session.add(u2)
    db_session.commit()
    db_session.refresh(u2)

    # Make an authenticated client for user 2
    from app.main import app
    from app.auth.dependencies import get_current_user
    
    app.dependency_overrides[get_current_user] = lambda: u2
    
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # User 2 gets their own defaults, not User 1's true setting
            response = await ac.get("/api/v1/notifications/preferences")
            assert response.status_code == 200
            data = response.json()
            assert data["email_enabled"] is False
            assert data["user_id"] == str(u2.id)
            
            # User 2 sets to false explicitly (already false but let's change severity to low)
            await ac.put("/api/v1/notifications/preferences", json={"min_severity_email": "low"})
            
    finally:
        # Restore test_user override so other tests aren't messed up
        app.dependency_overrides[get_current_user] = lambda: test_user
    
    # User 1's preferences should remain untouched
    response1 = await authorized_client.get("/api/v1/notifications/preferences")
    assert response1.json()["email_enabled"] is True
    assert response1.json()["min_severity_email"] == "high" # original was critical in prev test, wait, these are isolated tests. Default string was "high"

@pytest.mark.asyncio
async def test_unauthenticated_requests_rejected(async_client):
    response = await async_client.get("/api/v1/notifications/preferences")
    assert response.status_code == 401
    
    response2 = await async_client.put(
        "/api/v1/notifications/preferences",
        json={"email_enabled": True}
    )
    assert response2.status_code == 401
