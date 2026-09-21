from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.schemas.notification_preference import NotificationPreferenceRead, NotificationPreferenceUpdate
from app.services import notification_preference_service

router = APIRouter()

@router.get("/preferences", response_model=NotificationPreferenceRead)
def get_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get current user's notification preferences.
    Auto-creates default preferences on first read.
    """
    return notification_preference_service.get_or_create_preference(db=db, user_id=current_user.id)

@router.put("/preferences", response_model=NotificationPreferenceRead)
def update_preferences(
    preference_in: NotificationPreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update current user's notification preferences.
    """
    return notification_preference_service.update_preference(
        db=db,
        user_id=current_user.id,
        update_data=preference_in.model_dump(exclude_unset=True)
    )
