from typing import List, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import Notification
from app.services import notification_service

router = APIRouter()

class UnreadCountResponse(BaseModel):
    count: int

class MarkAllReadResponse(BaseModel):
    count: int

@router.get(
    "",
    response_model=List[Notification],
)
def get_notifications(
    unread_only: bool = Query(False, description="Filter for unread notifications only"),
    before: Optional[datetime] = Query(None, description="Cursor for pagination (creation time)"),
    limit: int = Query(25, lte=100, description="Number of notifications to return"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Notification]:
    return notification_service.list_notifications(
        db=db,
        user_id=user.id,
        unread_only=unread_only,
        before=before,
        limit=limit,
    )

@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
)
def get_unread_count(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UnreadCountResponse:
    count = notification_service.get_unread_count(db=db, user_id=user.id)
    return UnreadCountResponse(count=count)

@router.post(
    "/{notification_id}/read",
    response_model=Notification,
)
def mark_notification_read(
    notification_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Notification:
    try:
        return notification_service.mark_read(
            db=db,
            notification_id=notification_id,
            user_id=user.id,
        )
    except HTTPException as e:
        if e.status_code == status.HTTP_403_FORBIDDEN:
            # We must mask authorization errors as 404 to avoid information leakage,
            # ensuring users only see what they own.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        raise e

@router.post(
    "/read-all",
    response_model=MarkAllReadResponse,
)
def mark_all_notifications_read(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MarkAllReadResponse:
    count = notification_service.mark_all_read(db=db, user_id=user.id)
    return MarkAllReadResponse(count=count)
