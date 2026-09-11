import os
import pytest

os.environ["GITHUB_APP_ID"] = "12345"
os.environ["GITHUB_APP_SLUG"] = "test-app"
os.environ["GITHUB_APP_PRIVATE_KEY"] = "test-pem"
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")

from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
