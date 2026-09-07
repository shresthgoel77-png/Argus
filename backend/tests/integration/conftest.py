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
    # Setup test engine
    test_engine = create_engine(settings.database_url, pool_pre_ping=True)
    
    # Run alembic upgrade head using programmatic API
    alembic_cfg = alembic.config.Config("alembic.ini")
    alembic_cfg.set_main_option("script_location", "alembic")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    
    alembic.command.upgrade(alembic_cfg, "head")
    
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
