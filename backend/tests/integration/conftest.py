import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
import alembic.config
import alembic.command

# Override environment for tests
settings.app_env = "test"
# Ensure the TEST_DATABASE_URL is used
if not settings.test_database_url:
    raise ValueError("TEST_DATABASE_URL environment variable must be provided for integration tests.")

settings.database_url = settings.test_database_url

@pytest.fixture(scope="session")
def engine():
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    test_engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
    
    # Run alembic upgrade head using programmatic API
    alembic_cfg = alembic.config.Config("alembic.ini")
    alembic_cfg.set_main_option("script_location", "alembic")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    
    # alembic.command.upgrade(alembic_cfg, "head")
    
    # Fallback to create_all to ensure all models are fully registered (in case migrations lag)
    from app.db.base_class import Base
    # import all models to register them
    from app.models.user import User
    from app.models.github_connection import GitHubConnection
    from app.models.repository import Repository
    from app.models.finding import Finding
    from app.models.notification import Notification
    from app.models.notification_preference import NotificationPreference
    Base.metadata.create_all(bind=test_engine)
    
    yield test_engine
    
    test_engine.dispose()

@pytest.fixture(scope="session")
def SessionLocal(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session(engine, SessionLocal):
    """
    Creates a fresh sqlalchemy session for each test that operates in a
    transaction. The transaction is rolled back at the end of the test,
    ensuring a clean state for the next test.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()
 
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
