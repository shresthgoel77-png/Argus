from tests.integration.conftest import * 
@pytest.fixture
def test_user(db_session):
    import uuid
    from app.models.user import User
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



import pytest_asyncio

@pytest.fixture
def test_user_connection(db_session, test_user):
    from app.models.github_connection import GitHubConnection
    import uuid
    conn = GitHubConnection(
        id=uuid.uuid4(),
        user_id=test_user.id,
        installation_id=123456,
        account_login="test-org",
        account_type="Organization",
        status="active"
    )
    db_session.add(conn)
    db_session.commit()
    db_session.refresh(conn)
    return conn

@pytest.fixture
def test_user_repository(db_session, test_user_connection):
    from app.models.repository import Repository
    import uuid
    repo = Repository(
        id=uuid.uuid4(),
        connection_id=test_user_connection.id,
        github_repo_id=12345,
        full_name="test-org/test-repo",
        default_branch="main",
        monitoring_enabled=True,
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    return repo

@pytest_asyncio.fixture
async def async_client(client):
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest_asyncio.fixture
async def authorized_client(async_client, test_user, db_session):
    from app.main import app
    from app.auth.dependencies import get_current_user
    from app.db.session import get_db
    
    def override_get_current_user():
        return test_user
        
    def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db
    yield async_client
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)
