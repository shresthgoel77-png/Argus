import uuid
import pytest
from app.models.user import User
from app.models.github_connection import GitHubConnection
from app.services.github_connection_service import (
    upsert_connection_from_installation,
    list_connections_for_user,
    get_connection_or_404,
    handle_installation_status_change
)
from app.core.exceptions import NotFoundError

class MockGitHubAppClient:
    """Mock client for testing."""
    def __init__(self, login="test-org", acc_type="Organization"):
        self.login = login
        self.acc_type = acc_type
        
    async def get_installation(self, installation_id: int):
        return {
            "account": {
                "login": self.login,
                "type": self.acc_type
            }
        }

@pytest.fixture
def test_user(db_session):
    u = User(
        email=f"test_{uuid.uuid4()}@example.com",
        display_name="Test User",
        auth_provider="development",
        external_auth_id=str(uuid.uuid4())
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u

@pytest.fixture
def mock_client():
    return MockGitHubAppClient()

@pytest.mark.asyncio
async def test_upsert_connection_new(db_session, test_user, mock_client):
    inst_id = 999111
    
    connection = await upsert_connection_from_installation(
        db_session, test_user.id, inst_id, mock_client
    )
    
    assert connection.user_id == test_user.id
    assert connection.installation_id == inst_id
    assert connection.account_login == "test-org"
    assert connection.account_type == "Organization"
    assert connection.status == "active"
    
@pytest.mark.asyncio
async def test_upsert_connection_idempotent_update(db_session, test_user):
    mock_client = MockGitHubAppClient(login="test-org", acc_type="Organization")
    inst_id = 999222
    
    # First creation
    connection1 = await upsert_connection_from_installation(
        db_session, test_user.id, inst_id, mock_client
    )
    
    # Simulating update via reinstall
    mock_client.login = "test-org-renamed"
    connection2 = await upsert_connection_from_installation(
        db_session, test_user.id, inst_id, mock_client
    )
    
    assert connection1.id == connection2.id
    assert connection2.account_login == "test-org-renamed"

@pytest.mark.asyncio
async def test_upsert_connection_ownership_reassignment(db_session, test_user):
    user2 = User(
        email=f"test_{uuid.uuid4()}@example.com",
        display_name="User 2",
        auth_provider="development",
        external_auth_id=str(uuid.uuid4())
    )
    db_session.add(user2)
    db_session.commit()
    
    mock_client = MockGitHubAppClient()
    inst_id = 999333
    
    # Initially user1 installs
    connection1 = await upsert_connection_from_installation(
        db_session, test_user.id, inst_id, mock_client
    )
    
    # User2 re-authorizes same installation
    connection2 = await upsert_connection_from_installation(
        db_session, user2.id, inst_id, mock_client
    )
    
    assert connection1.id == connection2.id
    assert connection2.user_id == user2.id

def test_list_connections(db_session, test_user):
    inst_id_1 = 999441
    inst_id_2 = 999442
    
    conn1 = GitHubConnection(
        user_id=test_user.id,
        installation_id=inst_id_1,
        account_login="org1",
        account_type="Organization"
    )
    conn2 = GitHubConnection(
        user_id=test_user.id,
        installation_id=inst_id_2,
        account_login="org2",
        account_type="Organization"
    )
    db_session.add_all([conn1, conn2])
    db_session.commit()
    
    conns = list_connections_for_user(db_session, test_user.id)
    assert len(conns) == 2
    assert {c.installation_id for c in conns} == {inst_id_1, inst_id_2}

def test_get_connection_or_404(db_session, test_user):
    user2 = User(
        email=f"test_{uuid.uuid4()}@example.com",
        display_name="User 2",
        auth_provider="development",
        external_auth_id=str(uuid.uuid4())
    )
    db_session.add(user2)
    
    conn1 = GitHubConnection(
        user_id=test_user.id,
        installation_id=999551,
        account_login="org1",
        account_type="Organization"
    )
    db_session.add(conn1)
    db_session.commit()
    db_session.refresh(conn1)
    
    # Should succeed for correct user
    retrieved = get_connection_or_404(db_session, test_user.id, conn1.id)
    assert retrieved.id == conn1.id
    
    # Should raise error for wrong user
    with pytest.raises(NotFoundError):
        get_connection_or_404(db_session, user2.id, conn1.id)
        
    # Should raise error for non-existent connection
        get_connection_or_404(db_session, test_user.id, uuid.uuid4())

def test_handle_installation_status_change(db_session, test_user):
    inst_id = 999661
    conn = GitHubConnection(
        user_id=test_user.id,
        installation_id=inst_id,
        account_login="org1",
        account_type="Organization",
        status="active"
    )
    db_session.add(conn)
    db_session.commit()
    
    # action deleted -> removed
    updated = handle_installation_status_change(db_session, inst_id, "deleted")
    assert updated.status == "removed"
    
    # action suspend -> suspended
    updated = handle_installation_status_change(db_session, inst_id, "suspend")
    assert updated.status == "suspended"
    
    # action unsuspend -> active
    updated = handle_installation_status_change(db_session, inst_id, "unsuspend")
    assert updated.status == "active"
    
    # unrecognized action -> no change
    updated = handle_installation_status_change(db_session, inst_id, "random_action")
    assert updated.status == "active"
    
    # unrecognized id -> None
    missing = handle_installation_status_change(db_session, 123456789, "deleted")
    assert missing is None
