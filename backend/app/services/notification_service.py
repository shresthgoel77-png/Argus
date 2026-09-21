from typing import List, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, desc, update
from fastapi import HTTPException, status

from app.models.notification import Notification
from app.schemas.notification import NotificationCreate

def create_notification(db: Session, notification_in: NotificationCreate) -> Notification:
    db_obj = Notification(
        user_id=notification_in.user_id,
        repository_id=notification_in.repository_id,
        notification_type=notification_in.notification_type,
        severity=notification_in.severity,
        title=notification_in.title,
        message=notification_in.message,
        reference_type=notification_in.reference_type,
        reference_id=notification_in.reference_id,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def list_notifications(
    db: Session, 
    user_id: UUID, 
    unread_only: bool = False, 
    before: Optional[datetime] = None, 
    limit: int = 25
) -> List[Notification]:
    query = select(Notification).where(Notification.user_id == user_id)
    
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
        
    if before:
        query = query.where(Notification.created_at < before)
        
    query = query.order_by(desc(Notification.created_at)).limit(limit)
    
    result = db.execute(query)
    return list(result.scalars().all())

def get_unread_count(db: Session, user_id: UUID) -> int:
    query = select(func.count(Notification.id)).where(
        and_(
            Notification.user_id == user_id,
            Notification.read_at.is_(None)
        )
    )
    result = db.execute(query)
    return result.scalar() or 0

def mark_read(db: Session, notification_id: UUID, user_id: UUID) -> Notification:
    query = select(Notification).where(Notification.id == notification_id)
    result = db.execute(query)
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
        
    if notification.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this notification"
        )
        
    if notification.read_at is None:
        notification.read_at = func.now()
        db.add(notification)
        db.commit()
        db.refresh(notification)
        
    return notification

def mark_all_read(db: Session, user_id: UUID) -> int:
    stmt = (
        update(Notification)
        .where(
            and_(
                Notification.user_id == user_id,
                Notification.read_at.is_(None)
            )
        )
        .values(read_at=func.now())
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount
