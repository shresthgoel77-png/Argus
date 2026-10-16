import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import get_db

@pytest.fixture
def client(db_session):
    """
    Provides a TestClient instance where the get_db dependency 
    is overridden to use the isolated db_session fixture from conftest.
    """
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

def test_auth_flow_e2e(client):
    """
    Development login is not an application route; unauthenticated requests
    remain unauthorized and cannot provision a development user.
    """
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
    response = client.post("/api/v1/auth/dev-login")
    assert response.status_code == 404
