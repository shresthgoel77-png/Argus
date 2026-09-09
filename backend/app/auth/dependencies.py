from fastapi import Depends, Request
from sqlalchemy.orm import Session
from app.models.user import User
from app.db.session import get_db
from app.auth.factory import get_auth_provider
from app.core.exceptions import NotAuthenticatedError
from app.services.user_service import get_or_create_user_from_context

async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """
    Resolves the incoming user identity via the active AuthProvider.
    If authenticated, returns the internal User model instance (auto-provisioned if necessary).
    Otherwise, raises NotAuthenticatedError (returns 401).
    """
    provider = get_auth_provider()
    auth_context = await provider.resolve_identity(request)
    
    if not auth_context:
        raise NotAuthenticatedError()
        
    user = get_or_create_user_from_context(db, auth_context)
    return user
