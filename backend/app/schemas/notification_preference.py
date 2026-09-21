import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.notification_preference import NotificationSeverity

class NotificationPreferenceBase(BaseModel):
    email_enabled: bool = False
    min_severity_email: NotificationSeverity = NotificationSeverity.high

class NotificationPreferenceUpdate(BaseModel):
    email_enabled: bool | None = None
    min_severity_email: NotificationSeverity | None = None

class NotificationPreferenceRead(NotificationPreferenceBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
