import uuid
from datetime import datetime
from sqlalchemy import Integer, ForeignKey, JSON, Index, text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING, Any
from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.repository import Repository

class RepositoryHealthSnapshot(Base):
    __tablename__ = "repository_health_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repositories.id"), index=True, nullable=False)
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)
    category_scores: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    computed_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    __table_args__ = (
        Index(
            "ix_repository_health_snapshots_repo_computed_at",
            "repository_id",
            text("computed_at DESC"),
        ),
    )

    repository: Mapped["Repository"] = relationship()
