import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Text, Index, func, text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING
from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.repository import Repository

class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    repository_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=True
    )
    
    notification_type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    reference_type: Mapped[str] = mapped_column(String, nullable=False)
    reference_id: Mapped[str] = mapped_column(String, nullable=False)
    
    read_at: Mapped[datetime | None] = mapped_column(nullable=True)
    
    email_status: Mapped[str] = mapped_column(String, default="not_applicable", nullable=False)
    email_sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    email_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "notification_type IN ('finding_created', 'health_score_dropped')",
            name="ck_notifications_notification_type"
        ),
        CheckConstraint(
            "reference_type IN ('finding', 'health_snapshot')",
            name="ck_notifications_reference_type"
        ),
        CheckConstraint(
            "email_status IN ('not_applicable', 'pending', 'sent', 'failed')",
            name="ck_notifications_email_status"
        ),
        Index(
            "ix_notifications_user_id_read_at",
            "user_id",
            "read_at"
        ),
        Index(
            "ix_notifications_user_id_created_at_desc",
            "user_id",
            text("created_at DESC")
        ),
    )

    user: Mapped["User"] = relationship()
    repository: Mapped["Repository"] = relationship()
