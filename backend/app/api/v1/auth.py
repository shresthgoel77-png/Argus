from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserRead
from app.auth.dependencies import get_current_user
from app.auth.factory import get_auth_provider
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.services.user_service import get_or_create_user_from_context

router = APIRouter(prefix="/auth", tags=["auth"])

@router.get("/me", response_model=UserRead)
async def get_me(user: User = Depends(get_current_user)):
    """Returns the currently authenticated user."""
    return user

@router.post("/dev-login", response_model=UserRead)
async def dev_login(request: Request, db: Session = Depends(get_db)):
    """Logs in using the development adapter and returns the provisioned dev user."""
    provider = get_auth_provider()
    
    # Must explicitly check the class name or type
    if provider.__class__.__name__ != "DevelopmentAuthProvider":
        raise NotFoundError(message="Development login is not available in this environment.")
        
    await provider.login(request)
    
    # After login, resolve identity to trigger provisioning
    auth_context = await provider.resolve_identity(request)
    if not auth_context:
        # Should not happen if login succeeded and dev adapter is working
        raise NotFoundError(message="Failed to resolve identity after login.")
        
    user = get_or_create_user_from_context(db, auth_context)
    return user

@router.post("/logout")
async def logout(request: Request):
    """Provider-agnostic logout endpoint."""
    provider = get_auth_provider()
    await provider.logout(request)
    return {"status": "success", "message": "Logged out successfully"}
