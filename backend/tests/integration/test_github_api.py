import pytest
import uuid
import time
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import get_db
from app.integrations.github.install_state import get_serializer

@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

def test_github_install_flow(client, monkeypatch):
    """
    Test the GitHub app installation token generation and callback handler.
    """
    # 1. Dev login to get authenticated session
    res_login = client.post("/api/v1/auth/dev-login")
    assert res_login.status_code == 200

    # 2. Get install start URL
    res_start = client.get("/api/v1/github/install/start")
    assert res_start.status_code == 200
    install_url = res_start.json()["install_url"]
    assert "?state=" in install_url

    # Extract state from URL
    state = install_url.split("?state=")[1]

    # 3. Mock GitHubAppClient to avoid real network calls
    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

        async def get_installation(self, installation_id):
            return {"account": {"login": "octocat", "type": "User"}}

        async def list_installation_repositories(self):
            return [
                {
                    "id": 5001,
                    "full_name": "octocat/hello-world",
                    "private": False,
                    "default_branch": "main",
                },
            ]

    monkeypatch.setattr("app.api.v1.github.GitHubAppClient", MockClient)
    
    # 4. Successful callback
    res_callback = client.get(
        f"/api/v1/github/install/callback?installation_id=12345&setup_action=install&state={state}"
    )
    assert res_callback.status_code == 200
    connection = res_callback.json()
    assert connection["account_login"] == "octocat"
    assert connection["installation_id"] == 12345

    # Idempotency check: Calling it again with same params should still succeed
    res_callback2 = client.get(
        f"/api/v1/github/install/callback?installation_id=12345&setup_action=install&state={state}"
    )
    assert res_callback2.status_code == 200

    # 5. Get connections
    res_connections = client.get("/api/v1/github/connections")
    assert res_connections.status_code == 200
    connections_list = res_connections.json()
    assert len(connections_list) >= 1
    assert any(c["installation_id"] == 12345 for c in connections_list)

    # 6. Installation sync persists authorized repositories for the user
    res_repos = client.get("/api/v1/repositories")
    assert res_repos.status_code == 200
    repos = res_repos.json()
    assert any(r["full_name"] == "octocat/hello-world" for r in repos)

    # Idempotent re-callback does not duplicate repository rows
    res_repos2 = client.get("/api/v1/repositories")
    assert len(res_repos2.json()) == len(repos)

def test_github_install_callback_rejections(client):
    """
    Test failure cases for the callback handler (invalid state, wrong user).
    """
    client.post("/api/v1/auth/dev-login")
    
    res_missing = client.get("/api/v1/github/install/callback")
    assert res_missing.status_code == 400
    
    # Missing only installation_id
    res_missing_id = client.get("/api/v1/github/install/callback?setup_action=install&state=foo")
    assert res_missing_id.status_code == 400 

    res_invalid_state = client.get(
        "/api/v1/github/install/callback?installation_id=12345&setup_action=install&state=invalid.state.sig"
    )
    assert res_invalid_state.status_code == 400
    assert "signature" in res_invalid_state.json()["detail"].lower()

    from unittest.mock import patch
    with patch("app.api.v1.github.verify_install_state", side_effect=ValueError("Installation state has expired")):
        res_expired_state = client.get(
            f"/api/v1/github/install/callback?installation_id=12345&setup_action=install&state=foo"
        )
        assert res_expired_state.status_code == 400
        assert "expired" in res_expired_state.json()["detail"].lower()

    serializer = get_serializer()
    wrong_user_id = str(uuid.uuid4())
    wrong_payload = {"user_id": wrong_user_id, "issued_at": time.time()}
    wrong_state = serializer.dumps(wrong_payload)
    
    res_wrong_user = client.get(
        f"/api/v1/github/install/callback?installation_id=12345&setup_action=install&state={wrong_state}"
    )
    assert res_wrong_user.status_code == 400
    assert "different user" in res_wrong_user.json()["detail"].lower()

def test_github_endpoints_unauthenticated(client, monkeypatch):
    """
    The callback is allowed to validate a signed installation state without a
    Clerk bearer token; other GitHub endpoints remain protected.
    """
    assert client.get("/api/v1/github/install/start").status_code == 401
    assert client.get("/api/v1/github/connections").status_code == 401
    assert client.post("/api/v1/github/sync", json={"installation_id": "999"}).status_code == 401

    # Valid signed installation state should be accepted without a bearer token,
    # because it cryptographically binds the callback to the initiating RepoMedic user.
    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

        async def get_installation(self, installation_id):
            return {"account": {"login": "octocat", "type": "User"}}

        async def list_installation_repositories(self):
            return [{"id": 9001, "full_name": "octocat/redirected-repo", "private": False, "default_branch": "main"}]

    monkeypatch.setattr("app.api.v1.github.GitHubAppClient", MockClient)

    user = client.post("/api/v1/auth/dev-login")
    assert user.status_code == 200
    install_res = client.get("/api/v1/github/install/start")
    assert install_res.status_code == 200
    state = install_res.json()["install_url"].split("?state=")[1]

    res_callback = client.get(f"/api/v1/github/install/callback?installation_id=12345&setup_action=install&state={state}")
    assert res_callback.status_code == 200
    assert res_callback.json()["installation_id"] == 12345

    # Missing/invalid state still fails before any repository persistence.
    assert client.get("/api/v1/github/install/callback?installation_id=1&setup_action=install&state=foo").status_code == 400

def test_github_sync_flow(client, monkeypatch):
    """
    Test the GitHub app sync endpoint for existing installations.
    """
    client.post("/api/v1/auth/dev-login")
    
    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

        async def get_installation(self, installation_id):
            return {"account": {"login": "octocat_synced", "type": "User"}}

        async def list_installation_repositories(self):
            return [
                {
                    "id": 6001,
                    "full_name": "octocat_synced/app",
                    "private": True,
                    "default_branch": "main",
                },
            ]

    monkeypatch.setattr("app.api.v1.github.GitHubAppClient", MockClient)

    res = client.post("/api/v1/github/sync", json={"installation_id": "999999"})
    assert res.status_code == 200
    connection = res.json()
    assert connection["account_login"] == "octocat_synced"
    assert connection["installation_id"] == 999999

    res_repos = client.get("/api/v1/repositories")
    assert res_repos.status_code == 200
    assert any(r["full_name"] == "octocat_synced/app" for r in res_repos.json())

    # Missing payload test
    res_missing = client.post("/api/v1/github/sync", json={})
    assert res_missing.status_code == 422
