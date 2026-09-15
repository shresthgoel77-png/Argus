import uuid
from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING
from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.user import User

class AIConnection(Base):
    __tablename__ = "ai_connections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, default="valid", nullable=False)
    
    last_validated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    user: Mapped["User"] = relationship()
