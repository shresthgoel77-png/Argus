import uuid
from app.models.notification_preference import NotificationSeverity
from app.services.notification_preference_service import get_or_create_preference, update_preference

from tests.integration.conftest import *  # noqa: F401,F403

def test_get_or_create_preference_new_user(db_session):
    user_id = uuid.uuid4()
    
    # First time access creates defaults
    pref = get_or_create_preference(db_session, user_id)
    assert pref.user_id == user_id
    assert pref.email_enabled is False
    assert pref.min_severity_email == NotificationSeverity.high
    
    # Second time access returns the same defaults
    pref2 = get_or_create_preference(db_session, user_id)
    assert pref2.id == pref.id

def test_update_preference_round_trip(db_session):
    user_id = uuid.uuid4()
    
    # Update without pre-existing preference
    pref = update_preference(
        db_session,
        user_id,
        {"email_enabled": True, "min_severity_email": NotificationSeverity.critical}
    )
    
    assert pref.user_id == user_id
    assert pref.email_enabled is True
    assert pref.min_severity_email == NotificationSeverity.critical
    
    # Update existing preference
    pref2 = update_preference(
        db_session,
        user_id,
        {"email_enabled": False}
    )
    
    assert pref2.id == pref.id
    assert pref2.email_enabled is False
    assert pref2.min_severity_email == NotificationSeverity.critical # Should remain unchanged
