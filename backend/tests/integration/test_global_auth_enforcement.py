import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import get_db
from app.models.user import User
from app.models.github_connection import GitHubConnection
from app.models.repository import Repository
from app.auth.dependencies import get_current_user

@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

def test_unauthenticated_requests_uniformly_rejected(client: TestClient):
    """
    A sweep confirming every protected endpoint uniformly rejects unauthenticated requests with a 401.
    """
    endpoints = [
        ("GET", "/api/v1/auth/me"),
        ("GET", "/api/v1/github/install/start"),
        ("GET", "/api/v1/github/connections"),
        ("GET", f"/api/v1/github/connections/{uuid.uuid4()}/repositories"),
        ("POST", "/api/v1/repositories"),
        ("GET", "/api/v1/repositories"),
        ("PATCH", f"/api/v1/repositories/{uuid.uuid4()}"),
        ("GET", f"/api/v1/repositories/{uuid.uuid4()}/findings"),
        ("POST", f"/api/v1/repositories/{uuid.uuid4()}/refresh"),
        ("GET", f"/api/v1/repositories/{uuid.uuid4()}/activity"),
        ("POST", f"/api/v1/repositories/{uuid.uuid4()}/ai-summary"),
        ("GET", f"/api/v1/repositories/{uuid.uuid4()}/ai-summary/history"),
        ("GET", f"/api/v1/repositories/{uuid.uuid4()}/trends"),
        ("GET", f"/api/v1/repositories/{uuid.uuid4()}/dashboard"),
        ("GET", "/api/v1/findings"),
        ("GET", f"/api/v1/findings/{uuid.uuid4()}"),
        ("PATCH", f"/api/v1/findings/{uuid.uuid4()}"),
        ("POST", f"/api/v1/findings/{uuid.uuid4()}/ai-analysis"),
        ("GET", f"/api/v1/findings/{uuid.uuid4()}/ai-analysis/history"),
        ("GET", f"/api/v1/repositories/{uuid.uuid4()}/health"),
        ("GET", f"/api/v1/repositories/{uuid.uuid4()}/health/history"),
        ("POST", f"/api/v1/repositories/{uuid.uuid4()}/health-runs"),
        ("POST", f"/api/v1/repositories/{uuid.uuid4()}/monitor-runs"),
        ("GET", "/api/v1/notifications/preferences"),
        ("PUT", "/api/v1/notifications/preferences", {"email_enabled": True}),
        ("GET", "/api/v1/notifications"),
        ("GET", "/api/v1/notifications/unread-count"),
        ("POST", f"/api/v1/notifications/{uuid.uuid4()}/read"),
        ("POST", "/api/v1/notifications/read-all"),
        ("POST", "/api/v1/ai/connection", {"provider": "gemini", "api_key": "test"}),
        ("GET", "/api/v1/ai/connection"),
        ("DELETE", "/api/v1/ai/connection"),
        ("GET", f"/api/v1/repositories/{uuid.uuid4()}/bot-interactions")
    ]
    for e in endpoints:
        method = e[0]
        path = e[1]
        kwargs = {}
        if len(e) > 2:
            kwargs["json"] = e[2]
            
        res = client.request(method, path, **kwargs)
        assert res.status_code == 401, f"{method} {path} returned {res.status_code} instead of 401"


def test_ownership_scoping_with_clerk_mapped_user(client, db_session, monkeypatch):
    """
    Verify ownership boundaries hold for Clerk-mapped identities, not just dev-adapter.
    """
    # 1. Create a simulated clerk user
    clerk_user = User(
        email="clerk_owner@example.com",
        auth_provider="clerk",
        external_auth_id="user_2pabc123"
    )
    db_session.add(clerk_user)
    
    # 2. Create another user who owns some resources
    other_user = User(
        email="other@example.com",
        auth_provider="development",
        external_auth_id="dev_other"
    )
    db_session.add(other_user)
    db_session.commit()
    
    # Setup resources owned by `other_user`
    conn_other = GitHubConnection(
        user_id=other_user.id,
        installation_id=999,
        account_login="other_org",
        account_type="Organization"
    )
    db_session.add(conn_other)
    db_session.commit()
    
    repo_other = Repository(
        connection_id=conn_other.id,
        github_repo_id=999,
        full_name="other_org/repo",
        monitoring_enabled=True
    )
    db_session.add(repo_other)
    db_session.commit()
    
    # 3. Simulate Request authorized as Clerk user
    from app.auth.interfaces import AuthProvider
    from app.auth.context import AuthContext

    class MockClerkProvider(AuthProvider):
        async def resolve_identity(self, request):
            return AuthContext(
                external_id="user_2pabc123",
                email="clerk_owner@example.com",
                provider="clerk"
            )
        async def login(self, request, data=None): pass
        async def logout(self, request): pass

    def mock_get_auth_provider():
        return MockClerkProvider()

    monkeypatch.setattr("app.auth.dependencies.get_auth_provider", mock_get_auth_provider)
    
    # 4. Attempt to access other_user's resources and verify 404s
    res_repo_refresh = client.post(f"/api/v1/repositories/{repo_other.id}/refresh")
    assert res_repo_refresh.status_code == 404, "Cross-tenant repo refresh did not 404"
    
    res_repo_get = client.get(f"/api/v1/repositories/{repo_other.id}/dashboard")
    assert res_repo_get.status_code == 404, "Cross-tenant dashboard did not 404"
