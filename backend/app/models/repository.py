import uuid
from datetime import datetime, timezone
from sqlalchemy import BigInteger, String, Boolean, ForeignKey, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING
from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.github_connection import GitHubConnection

class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("github_connections.id"), index=True, nullable=False)
    github_repo_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_branch: Mapped[str | None] = mapped_column(String, nullable=True)
    monitoring_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    monitoring_status: Mapped[str] = mapped_column(
        String, default="disabled", server_default="disabled", nullable=False
    )
    monitoring_checks: Mapped[dict[str, dict[str, str | None]]] = mapped_column(
        JSON, default=dict, server_default="{}", nullable=False
    )
    last_monitoring_at: Mapped[datetime | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    connection: Mapped["GitHubConnection"] = relationship(back_populates="repositories")
