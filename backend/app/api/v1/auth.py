from fastapi import APIRouter, Depends, Request
from app.models.user import User
from app.schemas.user import UserRead
from app.auth.dependencies import get_current_user
from app.auth.factory import get_auth_provider

router = APIRouter(prefix="/auth", tags=["auth"])

@router.get("/me", response_model=UserRead)
async def get_me(user: User = Depends(get_current_user)):
    """Returns the currently authenticated user."""
    return user

@router.post("/logout")
async def logout(request: Request):
    """Provider-agnostic logout endpoint."""
    provider = get_auth_provider()
    await provider.logout(request)
    return {"status": "success", "message": "Logged out successfully"}
