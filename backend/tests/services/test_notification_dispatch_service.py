from unittest.mock import Mock, patch
import uuid

from app.models.notification import Notification
from app.models.notification_preference import NotificationSeverity
from app.services.notification_dispatch_service import dispatch_notification
from app.services.notification_preference_service import update_preference

from tests.integration.conftest import *  # noqa: F401,F403


def _dispatch(db_session, user_id, severity="high"):
    return dispatch_notification(
        db=db_session,
        user_id=user_id,
        repository_id=None,
        notification_type="finding_created",
        severity=severity,
        title="A finding",
        message="A message",
        reference_type="finding",
        reference_id=str(uuid.uuid4()),
    )


def test_email_enabled_and_severity_met_sends_email(db_session, test_user):
    update_preference(
        db_session,
        test_user.id,
        {"email_enabled": True, "min_severity_email": NotificationSeverity.high},
    )
    provider = Mock()
    provider.send.return_value = Mock(success=True)

    with patch("app.services.notification_dispatch_service.get_provider", return_value=Mock(return_value=provider)):
        notification = _dispatch(db_session, test_user.id)

    provider.send.assert_called_once()
    assert notification.email_status == "sent"
    assert notification.email_sent_at is not None
    assert notification.email_error_message is None


def test_email_disabled_does_not_send_email(db_session, test_user):
    provider = Mock()

    with patch("app.services.notification_dispatch_service.get_provider", return_value=Mock(return_value=provider)):
        notification = _dispatch(db_session, test_user.id)

    provider.send.assert_not_called()
    assert notification.email_status == "not_applicable"


def test_severity_below_threshold_does_not_send_email(db_session, test_user):
    update_preference(
        db_session,
        test_user.id,
        {"email_enabled": True, "min_severity_email": NotificationSeverity.high},
    )
    provider = Mock()

    with patch("app.services.notification_dispatch_service.get_provider", return_value=Mock(return_value=provider)):
        notification = _dispatch(db_session, test_user.id, severity="medium")

    provider.send.assert_not_called()
    assert notification.email_status == "not_applicable"


def test_provider_failure_is_persisted_without_propagating(db_session, test_user):
    update_preference(
        db_session,
        test_user.id,
        {"email_enabled": True, "min_severity_email": NotificationSeverity.high},
    )
    provider = Mock()
    provider.send.side_effect = RuntimeError("SMTP response contains secret details")

    with patch("app.services.notification_dispatch_service.get_provider", return_value=Mock(return_value=provider)):
        notification = _dispatch(db_session, test_user.id)

    persisted = db_session.query(Notification).filter(Notification.id == notification.id).one()
    assert persisted.email_status == "failed"
    assert persisted.email_error_message == "email_provider_exception"
    assert "SMTP response" not in persisted.email_error_message


def test_provider_returned_failure_is_persisted_without_raw_message(db_session, test_user):
    update_preference(
        db_session,
        test_user.id,
        {"email_enabled": True, "min_severity_email": NotificationSeverity.high},
    )
    provider = Mock()
    provider.send.return_value = Mock(
        success=False,
        error_message="SMTP response contains secret details",
    )

    with patch("app.services.notification_dispatch_service.get_provider", return_value=Mock(return_value=provider)):
        notification = _dispatch(db_session, test_user.id)

    assert notification.email_status == "failed"
    assert notification.email_error_message == "email_provider_failed"