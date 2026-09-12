import uuid
from datetime import datetime, timezone
from sqlalchemy import BigInteger, String, ForeignKey, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING, Any
from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.repository import Repository

class GitHubEvent(Base):
    __tablename__ = "github_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    delivery_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str | None] = mapped_column(String, nullable=True)
    installation_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    repository_github_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    repository_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("repositories.id"), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String, default="received", nullable=False)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    received_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(nullable=True)
