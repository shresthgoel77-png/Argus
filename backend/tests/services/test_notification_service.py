import uuid
from datetime import datetime
import pytest
from fastapi import HTTPException

from app.schemas.notification import NotificationCreate
from app.services.notification_service import (
    create_notification,
    list_notifications,
    get_unread_count,
    mark_read,
    mark_all_read
)

from tests.integration.conftest import *  # noqa: F401,F403

def test_create_and_list_notifications(db_session):
    user_id = uuid.uuid4()
    
    # Create notification 1
    notif1 = create_notification(
        db_session,
        NotificationCreate(
            user_id=user_id,
            notification_type="finding_created",
            severity="high",
            title="Finding 1",
            message="Message 1",
            reference_type="finding",
            reference_id=str(uuid.uuid4())
        )
    )
    
    # Create notification 2
    notif2 = create_notification(
        db_session,
        NotificationCreate(
            user_id=user_id,
            notification_type="health_score_dropped",
            severity="critical",
            title="Score dropped",
            message="Message 2",
            reference_type="health_snapshot",
            reference_id=str(uuid.uuid4())
        )
    )
    
    assert notif1.id is not None
    assert notif2.id is not None
    assert notif1.user_id == user_id
    
    # List notifications (order by created_at desc)
    notifications = list_notifications(db_session, user_id=user_id)
    assert len(notifications) == 2
    
    # Unread count
    assert get_unread_count(db_session, user_id=user_id) == 2
    
def test_mark_read_and_permissions(db_session):
    user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    
    notif = create_notification(
        db_session,
        NotificationCreate(
            user_id=user_id,
            notification_type="finding_created",
            severity="low",
            title="Low finding",
            message="Message",
            reference_type="finding",
            reference_id="some-id"
        )
    )
    
    # Wrong user tries to mark read
    with pytest.raises(HTTPException) as excinfo:
        mark_read(db_session, notif.id, other_user_id)
    assert excinfo.value.status_code == 403
    
    # Non existent
    with pytest.raises(HTTPException) as excinfo:
        mark_read(db_session, uuid.uuid4(), user_id)
    assert excinfo.value.status_code == 404
    
    # Correct mark read
    marked = mark_read(db_session, notif.id, user_id)
    assert marked.read_at is not None
    
    assert get_unread_count(db_session, user_id) == 0
    
def test_mark_all_read(db_session):
    user_id = uuid.uuid4()
    # create two
    for _ in range(2):
        create_notification(
            db_session,
            NotificationCreate(
                user_id=user_id,
                notification_type="finding_created",
                severity="low",
                title="title",
                message="msg",
                reference_type="finding",
                reference_id="ref"
            )
        )
        
    other_user_id = uuid.uuid4()
    create_notification(
        db_session,
        NotificationCreate(
            user_id=other_user_id,
            notification_type="finding_created",
            severity="low",
            title="title",
            message="msg",
            reference_type="finding",
            reference_id="ref"
        )
    )
    
    assert get_unread_count(db_session, user_id) == 2
    
    # mark all read
    updated_count = mark_all_read(db_session, user_id)
    assert updated_count == 2
    
    assert get_unread_count(db_session, user_id) == 0
    # other user unchanged
    assert get_unread_count(db_session, other_user_id) == 1
