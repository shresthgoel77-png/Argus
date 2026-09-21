from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.integrations.email import get_provider
from app.models.notification import Notification
from app.models.notification_preference import NotificationSeverity
from app.models.user import User
from app.schemas.notification import NotificationCreate
from app.services import notification_preference_service, notification_service

logger = get_logger(__name__)

_SEVERITY_RANK = {
    NotificationSeverity.critical.value: 0,
    NotificationSeverity.high.value: 1,
    NotificationSeverity.medium.value: 2,
    NotificationSeverity.low.value: 3,
    NotificationSeverity.info.value: 4,
}
_EMAIL_PROVIDER_KEY = "smtp"
_EMAIL_PROVIDER_FAILURE = "email_provider_failed"
_EMAIL_PROVIDER_EXCEPTION = "email_provider_exception"


def _severity_value(severity: str | NotificationSeverity) -> str:
    return severity.value if isinstance(severity, NotificationSeverity) else severity


def _email_gate_is_open(
    email_enabled: bool,
    severity: str | NotificationSeverity,
    minimum_severity: str | NotificationSeverity,
) -> bool:
    severity_value = _severity_value(severity)
    minimum_value = _severity_value(minimum_severity)
    return (
        email_enabled
        and severity_value in _SEVERITY_RANK
        and minimum_value in _SEVERITY_RANK
        and _SEVERITY_RANK[severity_value] <= _SEVERITY_RANK[minimum_value]
    )


def _persist_email_result(
    db: Session,
    notification: Notification,
    *,
    success: bool,
    error_message: str | None = None,
) -> None:
    notification.email_status = "sent" if success else "failed"
    notification.email_sent_at = datetime.now(timezone.utc) if success else None
    notification.email_error_message = None if success else error_message
    db.add(notification)
    db.commit()
    db.refresh(notification)


def dispatch_notification(
    db: Session,
    user_id: UUID,
    repository_id: UUID | None,
    notification_type: str,
    severity: str | NotificationSeverity,
    title: str,
    message: str,
    reference_type: str,
    reference_id: str,
) -> Notification:
    """Create an in-app notification and best-effort email notification."""
    notification = notification_service.create_notification(
        db,
        NotificationCreate(
            user_id=user_id,
            repository_id=repository_id,
            notification_type=notification_type,
            severity=_severity_value(severity),
            title=title,
            message=message,
            reference_type=reference_type,
            reference_id=reference_id,
        ),
    )

    try:
        preference = notification_preference_service.get_or_create_preference(db, user_id)
        if not _email_gate_is_open(
            preference.email_enabled,
            severity,
            preference.min_severity_email,
        ):
            return notification

        recipient = db.query(User).filter(User.id == user_id).one()
        provider = get_provider(_EMAIL_PROVIDER_KEY)()
        result = provider.send(
            to=recipient.email,
            subject=title,
            html_body=f"<p>{message}</p>",
            text_body=message,
        )
        if result.success:
            _persist_email_result(db, notification, success=True)
        else:
            _persist_email_result(
                db,
                notification,
                success=False,
                error_message=_EMAIL_PROVIDER_FAILURE,
            )
    except Exception:
        logger.warning(
            "Notification email dispatch failed",
            exc_info=True,
            extra={"notification_id": str(notification.id), "user_id": str(user_id)},
        )
        try:
            _persist_email_result(
                db,
                notification,
                success=False,
                error_message=_EMAIL_PROVIDER_EXCEPTION,
            )
        except Exception:
            logger.warning(
                "Failed to persist notification email failure",
                exc_info=True,
                extra={"notification_id": str(notification.id), "user_id": str(user_id)},
            )

    return notification