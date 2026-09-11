import uuid
from sqlalchemy.orm import Session
from app.models.github_connection import GitHubConnection
from app.integrations.github.client import GitHubAppClient
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger

logger = get_logger(__name__)

async def upsert_connection_from_installation(
    db: Session,
    user_id: uuid.UUID,
    installation_id: int,
    client: GitHubAppClient
) -> GitHubConnection:
    """
    Fetches installation metadata from GitHub via the client, then creates or
    updates a GitHubConnection record for this user and installation.
    If the installation_id is already bound to a different user, reassigns ownership
    and emits a structured log.
    """
    installation_data = await client.get_installation(installation_id)
    
    account_login = installation_data["account"]["login"]
    account_type = installation_data["account"]["type"]
    
    connection = db.query(GitHubConnection).filter(
        GitHubConnection.installation_id == installation_id
    ).first()
    
    if connection:
        if connection.user_id != user_id:
            logger.warning(
                "GitHub Connection ownership reassigned",
                extra={
                    "event": "github_connection_reassigned",
                    "installation_id": installation_id,
                    "old_user_id": str(connection.user_id),
                    "new_user_id": str(user_id),
                    "account_login": account_login,
                }
            )
            connection.user_id = user_id
            
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
