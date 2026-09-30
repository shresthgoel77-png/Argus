from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.models.user import User
from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.core.config import settings
from app.core.exceptions import NotAuthenticatedError
from app.integrations.github.install_state import generate_install_state, verify_install_state
from app.integrations.github.client import GitHubAppClient
from app.services.github_connection_service import (
    upsert_connection_from_installation,
    list_connections_for_user,
    get_connection_or_404
)
from app.schemas.github_connection import GitHubConnectionRead
from app.services.repository_service import (
    list_available_repositories,
    sync_installation_repositories,
)
from app.schemas.repository import AvailableRepository
import uuid

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
    request: Request,
    installation_id: str | None = None,
    setup_action: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db)
):
    """
    Handles the GitHub App installation callback.

    Browser-driven GitHub redirects do not include a Clerk bearer token, so the
    initiating RepoMedic user must be recovered from the signed installation
    state that was issued by start_installation(). This remains cryptographically
    bound to the correct user while avoiding a token requirement on the GitHub
    redirect itself.

    Browser-driven GitHub redirects expect the popup completion HTML because
    the frontend listens for the window.opener.postMessage event. Direct app
    fetches still expect the JSON connection payload used by the client callback
    page. The two modes are intentionally preserved.
    """
    if not installation_id or not installation_id.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing or malformed installation_id"
        )
    inst_id_int = int(installation_id)

    if not setup_action or setup_action not in ("install", "update"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported or missing setup_action"
        )

    if not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing state"
        )

    try:
        payload = verify_install_state(state)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    user_id_raw = payload.get("user_id")
    if not isinstance(user_id_raw, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Installation state is missing a valid user_id"
        )

    try:
        user_id = uuid.UUID(user_id_raw)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Installation state contains an invalid user_id"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State token belongs to a different user"
        )

    try:
        current_user = await get_current_user(request, db)
    except NotAuthenticatedError:
        current_user = None

    if current_user is not None and current_user.id != user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State token belongs to a different user"
        )

    async with GitHubAppClient(installation_id=inst_id_int) as client:
        connection = await upsert_connection_from_installation(
            db=db,
            user_id=user.id,
            installation_id=inst_id_int,
            client=client,
        )
        await sync_installation_repositories(db=db, connection=connection, client=client)

    accept_header = request.headers.get("accept", "")
    if "text/html" in accept_header.lower():
        return HTMLResponse(
            """
            <html>
              <body>
                <script>
                  if (window.opener) {
                    window.opener.postMessage({ type: 'github_install_success' }, window.location.origin);
                  }
                  window.close();
                </script>
              </body>
            </html>
            """
        )

    return connection

class GitHubSyncRequest(BaseModel):
    installation_id: str

@router.post("/sync", response_model=GitHubConnectionRead)
async def sync_installation(
    body: GitHubSyncRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Syncs an existing GitHub App installation that was installed from outside the typical browser flow
    (e.g., from the GitHub Marketplace), which does not return a state token.
    """
    if not body.installation_id or not body.installation_id.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing or malformed installation_id"
        )
    inst_id_int = int(body.installation_id)

    async with GitHubAppClient(installation_id=inst_id_int) as client:
        connection = await upsert_connection_from_installation(
            db=db,
            user_id=user.id,
            installation_id=inst_id_int,
            client=client,
        )
        await sync_installation_repositories(db=db, connection=connection, client=client)

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


@router.get("/connections/{connection_id}/repositories", response_model=list[AvailableRepository])
async def get_available_repositories(
    connection_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns the list of repositories available to the connection.
    Ownership is verified.
    """
    connection = get_connection_or_404(db=db, user_id=user.id, connection_id=connection_id)
    async with GitHubAppClient(installation_id=connection.installation_id) as client:
        return await list_available_repositories(db=db, connection=connection, client=client)
