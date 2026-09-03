import pytest
import time
import httpx
import os

# Set model for testing
os.environ["AI_MODEL"] = "gemini-2.5-flash"

@pytest.fixture
def SIMULATOR_URL():
    return os.getenv("SIMULATOR_URL", "http://localhost:9000")

@pytest.fixture
def BACKEND_URL():
    return os.getenv("BACKEND_URL", "http://localhost:8000")

@pytest.fixture
def generate_traffic(SIMULATOR_URL):
    def _generate(seconds: float):
        end_time = time.time() + seconds
        while time.time() < end_time:
            try:
                # Use httpx for consistency with other newer tests, ignoring exceptions to keep generating
                httpx.get(f"{SIMULATOR_URL}/api/checkout", timeout=1.0)
                httpx.post(f"{SIMULATOR_URL}/webhook/payment-event", json={}, timeout=1.0)
            except Exception:
                pass
            time.sleep(0.5)
    return _generate

@pytest.fixture
def security_db(monkeypatch):
    """
    Sets up an isolated SQLite database for security tests and provides a TestClient.
    This avoids duplicating the DB creation boilerplate in every test file.
    """
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db import Base, engine, SessionLocal
    from app.models import Evidence, Incident, RemediationAction
    
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test_security_suite.db")
    
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.query(RemediationAction).delete()
    db.query(Evidence).delete()
    db.query(Incident).delete()
    db.commit()
    db.close()
    
    yield TestClient(app)
    
    db = SessionLocal()
    db.query(RemediationAction).delete()
    db.query(Evidence).delete()
    db.query(Incident).delete()
    db.commit()
    db.close()

@pytest.fixture(autouse=True)
def cleanup_fastapi_tasks():
    """
    Ensures that any background tasks spawned by global TestClient instances
    are forcefully cancelled at test session shutdown to prevent anyio 
    event-loop hangs at teardown and cross-test background detection stealing.
    """
    yield
    from app.main import poll_task
    import sys
    if poll_task and not poll_task.done():
        poll_task.cancel()
