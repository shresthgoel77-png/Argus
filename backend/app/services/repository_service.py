import uuid
from sqlalchemy.orm import Session
from app.models.repository import Repository
from app.models.github_connection import GitHubConnection
from app.integrations.github.client import GitHubAppClient
from app.schemas.repository import AvailableRepository
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger

logger = get_logger(__name__)


async def list_available_repositories(
    db: Session, connection: GitHubConnection, client: GitHubAppClient
) -> list[AvailableRepository]:
    """
    Lists repositories available to the connection and flags which ones
    are already saved in the database.
    """
    github_repos = await client.list_installation_repositories()

    # Get already saved repositories for this connection
    saved_repos = (
        db.query(Repository.github_repo_id)
        .filter(Repository.connection_id == connection.id)
        .all()
    )
    saved_repo_ids = {r[0] for r in saved_repos}

    available_repos = []
    for repo in github_repos:
        available_repos.append(
            AvailableRepository(
                github_repo_id=repo["id"],
                full_name=repo["full_name"],
                private=repo["private"],
                default_branch=repo.get("default_branch"),
                already_added=repo["id"] in saved_repo_ids,
            )
        )

    return available_repos


async def add_repository(
    db: Session, connection: GitHubConnection, github_repo_id: int, client: GitHubAppClient
) -> Repository:
    """
    Adds a repository to the connection. Validates that the repository is actually
    accessible to the installation. Idempotent: returns existing if already added.
    """
    # Check if it already exists
    existing_repo = (
        db.query(Repository)
        .filter(
            Repository.connection_id == connection.id,
            Repository.github_repo_id == github_repo_id,
        )
        .first()
    )
    if existing_repo:
        logger.info(
            "Repository already added, returning existing.",
            extra={
                "github_repo_id": github_repo_id,
                "connection_id": str(connection.id),
            },
        )
        return existing_repo

    # Validate against GitHub API
    github_repos = await client.list_installation_repositories()
    accessible_repo = None
    for repo in github_repos:
        if repo["id"] == github_repo_id:
            accessible_repo = repo
            break

    if not accessible_repo:
        logger.warning(
            "Attempted to add repository not accessible to installation.",
            extra={
                "github_repo_id": github_repo_id,
                "connection_id": str(connection.id),
            },
        )
        raise NotFoundError("Repository not found in installation's accessible list.")

    # Create new repository record
    new_repo = Repository(
        connection_id=connection.id,
        github_repo_id=accessible_repo["id"],
        full_name=accessible_repo["full_name"],
        private=accessible_repo["private"],
        default_branch=accessible_repo.get("default_branch"),
        monitoring_enabled=False,
    )
    db.add(new_repo)
    db.commit()
    db.refresh(new_repo)

    logger.info(
        "Repository added successfully.",
        extra={
            "repository_id": str(new_repo.id),
            "github_repo_id": new_repo.github_repo_id,
            "connection_id": str(connection.id),
        },
    )
    return new_repo


def list_repositories_for_user(db: Session, user_id: uuid.UUID) -> list[Repository]:
    """
    Lists all saved repositories that belong to the user's connections.
    """
    return (
        db.query(Repository)
        .join(GitHubConnection)
        .filter(GitHubConnection.user_id == user_id)
        .all()
    )


def set_monitoring_enabled(
    db: Session, user_id: uuid.UUID, repository_id: uuid.UUID, enabled: bool
) -> Repository:
    """
    Toggles the monitoring_enabled field ensuring the repository belongs to the given user.
    """
    repository = (
        db.query(Repository)
        .join(GitHubConnection)
        .filter(
            Repository.id == repository_id,
            GitHubConnection.user_id == user_id,
        )
        .first()
    )

    if not repository:
        logger.warning(
            "Attempted to toggle monitoring on non-existent or unauthorized repository.",
            extra={"repository_id": str(repository_id), "user_id": str(user_id)},
        )
        raise NotFoundError("Repository not found or not owned by user.")

    repository.monitoring_enabled = enabled
    db.commit()
    db.refresh(repository)

    logger.info(
        "Monitoring toggled.",
        extra={
            "repository_id": str(repository.id),
            "monitoring_enabled": repository.monitoring_enabled,
        },
    )

    return repository
