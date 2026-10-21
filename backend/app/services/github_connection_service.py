import uuid
from fastapi import HTTPException
from clerk_backend_api import Clerk
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from app.models.github_connection import GitHubConnection
from app.models.repository import Repository
from app.models.user import User
from app.core.config import settings
from app.integrations.github.client import GitHubAppClient
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger

logger = get_logger(__name__)


async def verify_new_installation_account(user: User, account: dict) -> None:
    """A state token/installation number alone is not proof of GitHub ownership."""
    if user.auth_provider != "clerk" or not user.external_auth_id or not settings.clerk_secret_key:
        raise HTTPException(403, "Link the owning GitHub account to your Clerk profile before connecting it.")
    try:
        clerk = Clerk(bearer_auth=settings.clerk_secret_key.get_secret_value())
        identity = await run_in_threadpool(clerk.users.get, user_id=user.external_auth_id)
    except Exception as exc:
        raise HTTPException(502, "GitHub account ownership could not be verified with Clerk. Retry; no connection was changed.") from exc
    linked = any(
        external.provider in {"github", "oauth_github"}
        and str(external.provider_user_id) == str(account.get("id"))
        and getattr(external.verification, "status", None) == "verified"
        for external in getattr(identity, "external_accounts", [])
    )
    if account.get("type") != "User" or not linked:
        raise HTTPException(403, "The installation account is not a verified linked GitHub identity. Link the owning account in Clerk. New organization connections require verified organization authorization; no records were changed.")


def validate_installation_metadata(installation_data: dict, installation_id: int) -> dict:
    account = installation_data.get("account") or {}
    if (installation_data.get("id") != installation_id
            or str(installation_data.get("app_id")) != settings.github_app_id
            or not account.get("login") or account.get("type") not in {"User", "Organization"}):
        raise HTTPException(409, "GitHub returned an unexpected App, installation, or account. No records were changed.")
    if installation_data.get("suspended_at"):
        raise HTTPException(403, "Unsuspend this GitHub App installation in GitHub before reconnecting.")
    permissions = installation_data.get("permissions") or {}
    required = {"issues": "write", "pull_requests": "read", "contents": "read",
                "actions": "read", "administration": "read", "vulnerability_alerts": "read"}
    missing = [name for name, level in required.items()
               if permissions.get(name) not in ({"write"} if level == "write" else {"read", "write"})]
    if missing:
        raise HTTPException(403, "Approve the GitHub App repository permissions before reconnecting: " + ", ".join(missing))
    return account

async def upsert_connection_from_installation(
    db: Session,
    user_id: uuid.UUID,
    installation_id: int,
    client: GitHubAppClient,
    *,
    reconnect_connection_id: uuid.UUID | None = None,
) -> GitHubConnection:
    """
    Fetches installation metadata from GitHub via the client, then creates or
    updates a GitHubConnection record for this user and installation.
    Reconnection keeps the existing connection and repository IDs and ownership.
    All remote checks finish before any database mutation.
    """
    connection = db.query(GitHubConnection).filter(
        GitHubConnection.installation_id == installation_id
    ).first()
    if connection is not None and connection.user_id != user_id:
        raise HTTPException(403, "This installation belongs to another Argus user. No ownership was changed.")
    target = (get_connection_or_404(db, user_id, reconnect_connection_id)
              if reconnect_connection_id else connection)
    if connection is not None and target is not None and connection.id != target.id:
        raise HTTPException(409, "This installation is already bound to a different connection. No records were changed.")

    installation_data = await client.get_installation(installation_id)
    account = validate_installation_metadata(installation_data, installation_id)
    account_login, account_type = account["login"], account["type"]
    if target is not None:
        if target.account_login.casefold() != account_login.casefold() or target.account_type != account_type:
            raise HTTPException(403, "Reconnect the same GitHub account as the existing connection. No records were changed.")
    else:
        user = db.get(User, user_id)
        await verify_new_installation_account(user, account)

    accessible = await client.list_installation_repositories()
    accessible_ids = {repo["id"] for repo in accessible}
    if target is not None:
        saved = db.query(Repository).filter(Repository.connection_id == target.id).all()
        if any(repo.github_repo_id not in accessible_ids for repo in saved):
            raise HTTPException(403, "Include all existing connected repositories in this GitHub installation before reconnecting. No records were changed.")
    connection = target
    if connection:
        connection.installation_id = installation_id
        connection.account_login = account_login
        connection.account_type = account_type
        connection.status = "active"
    else:
        connection = GitHubConnection(
            user_id=user_id,
            installation_id=installation_id,
            account_login=account_login,
            account_type=account_type,
            status="active"
        )
        db.add(connection)
        
    db.commit()
    db.refresh(connection)
    
    return connection

def list_connections_for_user(db: Session, user_id: uuid.UUID) -> list[GitHubConnection]:
    """
    Returns all GitHub connections belonging to the specified user.
    """
    return db.query(GitHubConnection).filter(
        GitHubConnection.user_id == user_id
    ).all()

def get_connection_or_404(db: Session, user_id: uuid.UUID, connection_id: uuid.UUID) -> GitHubConnection:
    """
    Retrieves a single GitHub connection by ID, ensuring it belongs to the user_id.
    Raises NotFoundError if it doesn't exist or belongs to another user.
    """
    connection = db.query(GitHubConnection).filter(
        GitHubConnection.id == connection_id,
        GitHubConnection.user_id == user_id
    ).first()
    
    if not connection:
        raise NotFoundError("GitHub connection not found")
        
    return connection

def handle_installation_status_change(db: Session, installation_id: int, action: str) -> GitHubConnection | None:
    """
    Updates the connection status based on the installation webhook action.
    Returns None if the connection is not found.
    """
    connection = db.query(GitHubConnection).filter(
        GitHubConnection.installation_id == installation_id
    ).first()
    
    if not connection:
        return None
        
    if action == "deleted":
        connection.status = "removed"
    elif action == "suspend":
        connection.status = "suspended"
    elif action == "unsuspend":
        connection.status = "active"
    elif action == "new_permissions_accepted":
        pass
        
    db.commit()
    db.refresh(connection)
    
    return connection
