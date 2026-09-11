from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from app.models.user import User
from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.core.config import settings
from app.integrations.github.install_state import generate_install_state, verify_install_state
from app.integrations.github.client import GitHubAppClient
from app.services.github_connection_service import upsert_connection_from_installation, list_connections_for_user
from app.schemas.github_connection import GitHubConnectionRead

router = APIRouter(prefix="/github", tags=["github"])

@router.get("/install/start")
async def start_installation(user: User = Depends(get_current_user)):
    """
    Generates a state token and returns the installation URL.
    """
    state = generate_install_state(user.id)
    install_url = f"https://github.com/apps/{settings.github_app_slug}/installations/new?state={state}"
    return {"install_url": install_url}

@router.get("/install/callback", response_model=GitHubConnectionRead)
async def installation_callback(
    installation_id: int = Query(..., description="The GitHub installation ID"),
    setup_action: str = Query(..., description="The action performed (install, update)"),
    state: str = Query(..., description="The state token from the install/start endpoint"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Handles the GitHub App installation callback forwarding endpoint. 
    """
    if setup_action not in ("install", "update"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported setup_action: {setup_action}"
        )
        
    try:
        payload = verify_install_state(state)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
        
    if payload.get("user_id") != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State token belongs to a different user"
        )
        
    client = GitHubAppClient()
    connection = await upsert_connection_from_installation(
        db=db,
        user_id=user.id,
        installation_id=installation_id,
        client=client
    )
    
    return connection

@router.get("/connections", response_model=list[GitHubConnectionRead])
async def get_connections(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns the list of GitHub App connections for the authenticated user.
    """
    return list_connections_for_user(db=db, user_id=user.id)
