import uuid

from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
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
    cursor: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_repository_or_404(db=db, user_id=user.id, repository_id=repository_id)

    query = (
        db.query(BotInteraction)
        .filter(BotInteraction.repository_id == repository_id)
    )

    if cursor:
        import base64
        try:
            from sqlalchemy import or_, and_
            decoded = base64.urlsafe_b64decode(cursor.encode()).decode()
            cursor_dt_str, cursor_id_str = decoded.split(',')
            cursor_dt = datetime.fromisoformat(cursor_dt_str)
            cursor_id = uuid.UUID(cursor_id_str)
            query = query.filter(
                or_(
                    BotInteraction.created_at < cursor_dt,
                    and_(BotInteraction.created_at == cursor_dt, BotInteraction.id < cursor_id)
                )
            )
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid cursor")

    query = query.order_by(desc(BotInteraction.created_at), desc(BotInteraction.id))

    total = db.query(BotInteraction).filter(BotInteraction.repository_id == repository_id).count()
    interactions = query.limit(limit).all()

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
    next_cursor = None
    if len(interactions) == limit:
        import base64
        last = interactions[-1]
        next_cursor = base64.urlsafe_b64encode(f"{last.created_at.isoformat()},{last.id}".encode()).decode()

    return BotInteractionListResponse(
        items=items,
        total=total,
        limit=limit,
        next_cursor=next_cursor,
    )