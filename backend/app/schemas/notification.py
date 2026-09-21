from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime

class NotificationBase(BaseModel):
    repository_id: Optional[UUID] = None
    notification_type: str = Field(..., description="E.g. finding_created, health_score_dropped")
    severity: str
    title: str
    message: str
    reference_type: str = Field(..., description="E.g. finding, health_snapshot")
    reference_id: str

class NotificationCreate(NotificationBase):
    user_id: UUID

class NotificationUpdate(BaseModel):
    read_at: Optional[datetime] = None
    email_status: Optional[str] = None
    email_sent_at: Optional[datetime] = None
    email_error_message: Optional[str] = None

class Notification(NotificationBase):
    id: UUID
    user_id: UUID
    read_at: Optional[datetime]
    email_status: str
    email_sent_at: Optional[datetime]
    email_error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

