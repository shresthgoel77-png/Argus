import pytest
from sqlalchemy import text

def test_alembic_upgrade_head_completes(db_session):
    """
    Verifies that 'alembic upgrade head' applied migrations successfully.
    Since 'conftest.py' runs the migration setup via session fixture,
    we can query the 'alembic_version' table to ensure the database version
    is tracked.
    """
    result = db_session.execute(text("SELECT version_num FROM alembic_version"))
    version = result.scalar()
    
    assert version is not None, "Migrations were not run; 'alembic_version' table is missing or empty."

def test_alembic_downgrade_upgrade_smoke_test():
    import alembic.config
    import alembic.command
    from app.core.config import settings
    
    alembic_cfg = alembic.config.Config("alembic.ini")
    alembic_cfg.set_main_option("script_location", "alembic")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    
    # downgrade 1 revision
    alembic.command.downgrade(alembic_cfg, "-1")
    
    # upgrade back to head
    alembic.command.upgrade(alembic_cfg, "head")
