import uuid
from datetime import datetime
from sqlalchemy import BigInteger, String, ForeignKey, Text, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING
from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.repository import Repository
    from app.models.github_event import GitHubEvent

class BotInteraction(Base):
    __tablename__ = "bot_interactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False
    )
    github_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("github_events.id", ondelete="CASCADE"), index=True, unique=True, nullable=False
    )
    
    requester_github_login: Mapped[str] = mapped_column(String, nullable=False)
    intent: Mapped[str] = mapped_column(String, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    skip_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    github_reply_comment_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        Index(
            "ix_bot_interactions_repo_created_desc",
            "repository_id",
            text("created_at DESC"),
        ),
    )

    repository: Mapped["Repository"] = relationship()
    github_event: Mapped["GitHubEvent"] = relationship()
