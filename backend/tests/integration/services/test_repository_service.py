import uuid
import pytest
from app.services.repository_service import (
    list_available_repositories,
    add_repository,
    list_repositories_for_user,
    set_monitoring_enabled,
    disable_monitoring_for_removed_repositories
)
from app.models.github_connection import GitHubConnection
from app.models.repository import Repository
from app.core.exceptions import NotFoundError
from unittest.mock import AsyncMock, MagicMock
from app.integrations.github.client import GitHubAppClient
from app.integrations.github.webhook_events import RepoRef


@pytest.fixture
def mock_client():
    client = MagicMock(spec=GitHubAppClient)
    client.list_installation_repositories = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_list_available_repositories_flags_already_added(db_session, mock_client):
    user_id = uuid.uuid4()
    connection = GitHubConnection(
        user_id=user_id,
        installation_id=123,
        account_login="testuser",
        account_type="User",
        status="active",
    )
    db_session.add(connection)
    db_session.commit()

    # Pre-add one repository
    repo = Repository(
        connection_id=connection.id,
        github_repo_id=101,
        full_name="testuser/repo1",
        private=False,
        default_branch="main",
        monitoring_enabled=False,
    )
    db_session.add(repo)
    db_session.commit()

    # Mock github returning two repos
    mock_client.list_installation_repositories.return_value = [
        {"id": 101, "full_name": "testuser/repo1", "private": False, "default_branch": "main"},
        {"id": 102, "full_name": "testuser/repo2", "private": True, "default_branch": "master"},
    ]

    available = await list_available_repositories(db_session, connection, mock_client)

    assert len(available) == 2
    repo1 = next(r for r in available if r.github_repo_id == 101)
    repo2 = next(r for r in available if r.github_repo_id == 102)

    assert repo1.already_added is True
    assert repo2.already_added is False


@pytest.mark.asyncio
async def test_add_repository_idempotency(db_session, mock_client):
    user_id = uuid.uuid4()
    connection = GitHubConnection(
        user_id=user_id,
        installation_id=123,
        account_login="testuser",
        account_type="User",
        status="active",
    )
    db_session.add(connection)
    db_session.commit()

    mock_client.list_installation_repositories.return_value = [
        {"id": 101, "full_name": "testuser/repo1", "private": False, "default_branch": "main"},
    ]

    # First addition
    repo1 = await add_repository(db_session, connection, 101, mock_client)
    assert repo1.github_repo_id == 101

    # Second addition should be idempotent
    repo2 = await add_repository(db_session, connection, 101, mock_client)
    assert repo1.id == repo2.id


@pytest.mark.asyncio
async def test_add_repository_rejects_unauthorized(db_session, mock_client):
    user_id = uuid.uuid4()
    connection = GitHubConnection(
        user_id=user_id,
        installation_id=123,
        account_login="testuser",
        account_type="User",
        status="active",
    )
    db_session.add(connection)
    db_session.commit()

    mock_client.list_installation_repositories.return_value = [
        {"id": 101, "full_name": "testuser/repo1", "private": False, "default_branch": "main"},
    ]

    with pytest.raises(NotFoundError):
        await add_repository(db_session, connection, 999, mock_client)


def test_set_monitoring_enabled_ownership(db_session):
    user1_id = uuid.uuid4()
    user2_id = uuid.uuid4()

    connection1 = GitHubConnection(
        user_id=user1_id,
        installation_id=123,
        account_login="testuser1",
        account_type="User",
        status="active",
    )
    db_session.add(connection1)
    db_session.commit()

    repo = Repository(
        connection_id=connection1.id,
        github_repo_id=101,
        full_name="testuser1/repo1",
        private=False,
        default_branch="main",
        monitoring_enabled=False,
    )
    db_session.add(repo)
    db_session.commit()

    # User 1 can toggle it
    updated_repo = set_monitoring_enabled(db_session, user1_id, repo.id, True)
    assert updated_repo.monitoring_enabled is True

    # User 2 cannot toggle it
    with pytest.raises(NotFoundError):
        set_monitoring_enabled(db_session, user2_id, repo.id, False)

def test_disable_monitoring_for_removed_repositories(db_session):
    user_id = uuid.uuid4()
    connection = GitHubConnection(
        user_id=user_id,
        installation_id=123,
        account_login="testuser",
        account_type="User",
        status="active",
    )
    db_session.add(connection)
    db_session.commit()

    repo1 = Repository(
        connection_id=connection.id,
        github_repo_id=101,
        full_name="testuser/repo1",
        private=False,
        default_branch="main",
        monitoring_enabled=True,
    )
    repo2 = Repository(
        connection_id=connection.id,
        github_repo_id=102,
        full_name="testuser/repo2",
        private=False,
        default_branch="main",
        monitoring_enabled=True,
    )
    repo3 = Repository(
        connection_id=connection.id,
        github_repo_id=103,
        full_name="testuser/repo3",
        private=False,
        default_branch="main",
        monitoring_enabled=False,
    )
    db_session.add_all([repo1, repo2, repo3])
    db_session.commit()
    
    removed = [
        RepoRef(github_repo_id=101, full_name="testuser/repo1"),
        RepoRef(github_repo_id=103, full_name="testuser/repo3"),
        RepoRef(github_repo_id=999, full_name="testuser/repo999")
    ]
    
    affected = disable_monitoring_for_removed_repositories(db_session, connection, removed)
    
    assert len(affected) == 1
    assert affected[0].github_repo_id == 101
    assert repo1.monitoring_enabled is False
    assert repo2.monitoring_enabled is True
    assert repo3.monitoring_enabled is False
