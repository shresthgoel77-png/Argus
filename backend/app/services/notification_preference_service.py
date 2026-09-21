import uuid
from typing import Any, Dict
from sqlalchemy.orm import Session
from app.models.notification_preference import NotificationPreference, NotificationSeverity

def get_or_create_preference(db: Session, user_id: uuid.UUID) -> NotificationPreference:
    preference = db.query(NotificationPreference).filter_by(user_id=user_id).first()
    if not preference:
        preference = NotificationPreference(
            user_id=user_id,
            email_enabled=False,
            min_severity_email=NotificationSeverity.high
        )
        db.add(preference)
        db.commit()
        db.refresh(preference)
    return preference

def update_preference(
    db: Session, user_id: uuid.UUID, update_data: Dict[str, Any]
) -> NotificationPreference:
    preference = db.query(NotificationPreference).filter_by(user_id=user_id).first()
    
    if not preference:
        preference = NotificationPreference(
            user_id=user_id,
            email_enabled=False,
            min_severity_email=NotificationSeverity.high
        )
        db.add(preference)

    for field, value in update_data.items():
        if value is not None:
            setattr(preference, field, value)

    db.add(preference)
    db.commit()
    db.refresh(preference)
    return preference
