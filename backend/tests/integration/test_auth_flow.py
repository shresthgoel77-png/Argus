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
    Test the full end-to-end authentication flow using the development auth provider.
    Tests unauthenticated behaviour, dev-login, me, idempotency, and logout.
    """
    # 1. Unauthenticated GET /me returns 401
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
    
    # 2. POST /dev-login returns the deterministic dev user
    response = client.post("/api/v1/auth/dev-login")
    assert response.status_code == 200
    user_data = response.json()
    assert "email" in user_data
    assert "id" in user_data
    # Should not leak internal fields
    assert "external_auth_id" not in user_data
    
    # 3. GET /me returns the deterministic dev user
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    me_data = response.json()
    assert me_data["id"] == user_data["id"]
    
    # 4. Calling dev-login twice does not create duplicate User rows (idempotency check)
    response_2 = client.post("/api/v1/auth/dev-login")
    assert response_2.status_code == 200
    assert response_2.json()["id"] == user_data["id"]
    
    # 5. POST /logout
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    
    # 6. POST /logout then GET /me returns 401 again
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401

def test_dev_login_fails_non_development_provider(monkeypatch, client):
    """
    Test that forcing get_auth_provider to a non-development instance 
    makes dev-login return 404.
    """
    from app.auth.interfaces import AuthProvider
    
    class DummyProvider(AuthProvider):
        async def resolve_identity(self, request): return None
        async def login(self, request, data=None): return {}
        async def logout(self, request): return {}
        
    def mock_get_auth_provider():
        return DummyProvider()
        
    # Monkeypatch the factory function used in the route
    monkeypatch.setattr("app.api.v1.auth.get_auth_provider", mock_get_auth_provider)
    
    response = client.post("/api/v1/auth/dev-login")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
