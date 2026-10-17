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
    _score_data: Mapped[dict[str, Any]] = mapped_column("category_scores", JSON, nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    computed_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    @property
    def category_scores(self) -> dict[str, int]:
        return {key: value for key, value in (self._score_data or {}).items() if key != "_coverage"}

    @category_scores.setter
    def category_scores(self, scores: dict[str, int]) -> None:
        coverage = self.coverage
        self._score_data = dict(scores)
        if coverage is not None:
            self.coverage = coverage

    @property
    def coverage(self) -> dict[str, Any] | None:
        # Keep legacy rows unchanged: missing metadata means unknown coverage.
        return (self._score_data or {}).get("_coverage")

    @coverage.setter
    def coverage(self, coverage: dict[str, Any]) -> None:
        # Replace the JSON value so SQLAlchemy tracks the change.
        self._score_data = {**(self._score_data or {}), "_coverage": coverage}

    __table_args__ = (
        Index(
            "ix_repository_health_snapshots_repo_computed_at",
            "repository_id",
            text("computed_at DESC"),
        ),
    )

    repository: Mapped["Repository"] = relationship()
