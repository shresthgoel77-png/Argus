import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone
from app.models.user import User
from app.models.notification import Notification as NotificationModel
from app.main import app
from app.auth.dependencies import get_current_user

@pytest.fixture
def sample_notification(db_session, test_user):
    notification = NotificationModel(
        user_id=test_user.id,
        notification_type="finding_created",
        severity="high",
        title="Test",
        message="This is a test",
        reference_type="finding",
        reference_id="123"
    )
    db_session.add(notification)
    db_session.commit()
    db_session.refresh(notification)
    return notification

@pytest.mark.asyncio
async def test_get_notifications(authorized_client, sample_notification):
    # GET paginated and unfiltered
    res = await authorized_client.get("/api/v1/notifications")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    # Notification we created should be in list
    assert any(n["id"] == str(sample_notification.id) for n in data)
    
@pytest.mark.asyncio
async def test_get_notifications_unread_only(authorized_client, sample_notification):
    # GET unread
    res = await authorized_client.get("/api/v1/notifications?unread_only=true")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    assert any(n["id"] == str(sample_notification.id) for n in data)

@pytest.mark.asyncio
async def test_unread_count_and_mark_read(authorized_client, sample_notification):
    # Get unread count
    res_count = await authorized_client.get("/api/v1/notifications/unread-count")
    assert res_count.status_code == 200
    initial_count = res_count.json()["count"]
    assert initial_count >= 1

    # Mark as read
    res_read = await authorized_client.post(f"/api/v1/notifications/{sample_notification.id}/read")
    assert res_read.status_code == 200
    assert res_read.json()["read_at"] is not None

    # Get unread count again
    res_count_after = await authorized_client.get("/api/v1/notifications/unread-count")
    assert res_count_after.status_code == 200
    assert res_count_after.json()["count"] == initial_count - 1

@pytest.mark.asyncio
async def test_mark_all_read(authorized_client, db_session, test_user):
    # Create a couple of notifications
    n1 = NotificationModel(
        user_id=test_user.id,
        notification_type="finding_created",
        severity="high",
        title="T1",
        message="M1",
        reference_type="finding",
        reference_id="A"
    )
    n2 = NotificationModel(
        user_id=test_user.id,
        notification_type="health_score_dropped",
        severity="low",
        title="T2",
        message="M2",
        reference_type="health_snapshot",
        reference_id="B"
    )
    db_session.add_all([n1, n2])
    db_session.commit()

    # Get count before
    res_count = await authorized_client.get("/api/v1/notifications/unread-count")
    count_before = res_count.json()["count"]

    # Mark all read
    res_mark_all = await authorized_client.post("/api/v1/notifications/read-all")
    assert res_mark_all.status_code == 200
    assert res_mark_all.json()["count"] >= 2 # at least n1 and n2

    # Get count after
    res_count_after = await authorized_client.get("/api/v1/notifications/unread-count")
    assert res_count_after.json()["count"] == 0

@pytest.mark.asyncio
async def test_mark_read_ownership_scoping(authorized_client, db_session):
    u2 = User(
        email=f"scoping_test_{uuid.uuid4()}@example.com",
        display_name="Scoping User",
        auth_provider="development",
        external_auth_id=str(uuid.uuid4())
    )
    db_session.add(u2)
    db_session.commit()
    db_session.refresh(u2)
    
    n2 = NotificationModel(
        user_id=u2.id,
        notification_type="finding_created",
        severity="low",
        title="Not Yours",
        message="This belongs to U2",
        reference_type="finding",
        reference_id="C"
    )
    db_session.add(n2)
    db_session.commit()
    db_session.refresh(n2)
    
    # Try to mark another user's notification as read
    res = await authorized_client.post(f"/api/v1/notifications/{n2.id}/read")
    
    # We expect 404, not 403, as defined in requirements to avoid leaking existence
    assert res.status_code == 404

@pytest.mark.asyncio
async def test_get_notifications_ownership_scoping(authorized_client, db_session, test_user):
    u2 = User(
        email=f"scoping_get_{uuid.uuid4()}@example.com",
        display_name="Scoping Get User",
        auth_provider="development",
        external_auth_id=str(uuid.uuid4())
    )
    db_session.add(u2)
    db_session.commit()
    db_session.refresh(u2)
    
    n2 = NotificationModel(
        user_id=u2.id,
        notification_type="finding_created",
        severity="low",
        title="U2s",
        message="Only U2",
        reference_type="finding",
        reference_id="C"
    )
    db_session.add(n2)
    db_session.commit()

    # Now request with u2 token
    app.dependency_overrides[get_current_user] = lambda: u2
    try:
        res = await authorized_client.get("/api/v1/notifications")
        assert res.status_code == 200
        data = res.json()
        # Since u2 is completely new and only has n2, we should only see n2.
        # Even if test_user has 10 notifications, they shouldn't show up here
        assert len(data) == 1
        assert data[0]["id"] == str(n2.id)
    finally:
        app.dependency_overrides[get_current_user] = lambda: test_user
