import pytest
from sqlalchemy.exc import IntegrityError
from app.models.user import User
from app.models.github_connection import GitHubConnection
from app.models.repository import Repository
import uuid
import random

def test_valid_connection_and_repo(db_session):
    user = User(
        email=f"test_{uuid.uuid4()}@example.com",
        display_name="Test User",
        auth_provider="development",
        external_auth_id=str(uuid.uuid4())
    )
    db_session.add(user)
    db_session.commit()
    
    inst_id = random.randint(100000, 9999999999)
    connection = GitHubConnection(
        user_id=user.id,
        installation_id=inst_id,
        account_login="test_org",
        account_type="Organization"
    )
    db_session.add(connection)
    db_session.commit()
    db_session.refresh(connection)

    assert connection.status == "active"

    repo_id = random.randint(100000, 999999999)
    repo = Repository(
        connection_id=connection.id,
        github_repo_id=repo_id,
        full_name="test_org/test_repo",
        private=True,
        default_branch="main"
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    assert repo.monitoring_enabled is False

def test_duplicate_connection(db_session):
    user = User(
        email=f"test_{uuid.uuid4()}@example.com",
        display_name="Test User",
        auth_provider="development"
    )
    db_session.add(user)
    db_session.commit()
    
    inst_id = random.randint(100000, 9999999999)
    connection = GitHubConnection(
        user_id=user.id,
        installation_id=inst_id,
        account_login="org1",
        account_type="Organization"
    )
    db_session.add(connection)
    db_session.commit()
    
    dup_connection = GitHubConnection(
        user_id=user.id,
        installation_id=inst_id,
        account_login="org2",
        account_type="Organization"
    )
    db_session.add(dup_connection)
    with pytest.raises(IntegrityError):
        db_session.commit()

def test_duplicate_repo(db_session):
    user = User(
        email=f"test_{uuid.uuid4()}@example.com",
        display_name="Test User",
        auth_provider="development"
    )
    db_session.add(user)
    db_session.commit()
    
    connection = GitHubConnection(
        user_id=user.id,
        installation_id=random.randint(100000, 9999999999),
        account_login="org",
        account_type="Organization"
    )
    db_session.add(connection)
    db_session.commit()
    
    repo_id = random.randint(100000, 999999999)
    repo = Repository(
        connection_id=connection.id,
        github_repo_id=repo_id,
        full_name="org/repo1"
    )
    db_session.add(repo)
    db_session.commit()
    
    dup_repo = Repository(
        connection_id=connection.id,
        github_repo_id=repo_id,
        full_name="org/repo2"
    )
    db_session.add(dup_repo)
    with pytest.raises(IntegrityError):
        db_session.commit()
