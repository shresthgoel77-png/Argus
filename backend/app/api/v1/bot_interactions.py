import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.bot_interaction import BotInteraction
from app.models.user import User
from app.schemas.bot_interaction import (
    BotInteractionListResponse,
    BotInteractionResponse,
)
from app.services.repository_service import get_repository_or_404


router = APIRouter(prefix="/repositories/{repository_id}", tags=["bot-interactions"])


@router.get("/bot-interactions", response_model=BotInteractionListResponse)
def list_repository_bot_interactions(
    repository_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_repository_or_404(db=db, user_id=user.id, repository_id=repository_id)

    query = (
        db.query(BotInteraction)
        .filter(BotInteraction.repository_id == repository_id)
        .order_by(desc(BotInteraction.created_at), desc(BotInteraction.id))
    )
    total = query.count()
    interactions = query.limit(limit).offset(offset).all()

    items = [
        BotInteractionResponse(
            id=interaction.id,
            repository_id=interaction.repository_id,
            intent=interaction.intent,
            question_text=interaction.question_text[:500],
            status=interaction.status,
            skip_reason=interaction.skip_reason,
            response_text=(
                interaction.response_text
                if interaction.status == "completed"
                else None
            ),
            requester_github_login=interaction.requester_github_login,
            created_at=interaction.created_at,
            github_reply_comment_id=interaction.github_reply_comment_id,
        )
        for interaction in interactions
    ]
    return BotInteractionListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )