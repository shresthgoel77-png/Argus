from datetime import datetime
import uuid

from pydantic import BaseModel


class BotInteractionResponse(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    intent: str
    question_text: str
    status: str
    skip_reason: str | None
    response_text: str | None
    requester_github_login: str
    created_at: datetime
    github_reply_comment_id: int | None


class BotInteractionListResponse(BaseModel):
    items: list[BotInteractionResponse]
    total: int
    limit: int
    next_cursor: str | None = None