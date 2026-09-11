import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import get_db
from app.models.user import User
from app.models.github_connection import GitHubConnection
from app.models.repository import Repository

@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_repositories_endpoints_unauthenticated(client):
    """
    Test that all four repository endpoints reject unauthenticated access.
    """
    assert client.get(f"/api/v1/github/connections/{uuid.uuid4()}/repositories").status_code == 401
    assert client.get("/api/v1/repositories").status_code == 401
    assert client.post("/api/v1/repositories", json={"connection_id": str(uuid.uuid4()), "github_repo_id": 999}).status_code == 401
    assert client.patch(f"/api/v1/repositories/{uuid.uuid4()}", json={"monitoring_enabled": True}).status_code == 401


def test_repositories_happy_path(client, db_session, monkeypatch):
    """
    Full happy path:
    1. Dev Login
    2. Create a connection manually
    3. List available repositories (with mock GitHub client)
    4. Add a repository
    5. List persisted repositories
    6. Toggle monitoring
    """
    # 1. Login
    res_login = client.post("/api/v1/auth/dev-login")
    assert res_login.status_code == 200

    # Get the user that was just created/logged in by dev-login
    # dev-login typically creates a test user with a known email or just gets the first user
    user = db_session.query(User).first()
    
    # 2. Setup connection
    connection = GitHubConnection(
        user_id=user.id,
        installation_id=12345,
        account_login="test_org",
        account_type="Organization"
    )
    db_session.add(connection)
    db_session.commit()

    # 3. List available repos
    class MockClient:
        async def list_installation_repositories(self):
            return [
                {"id": 1001, "full_name": "test_org/repo1", "private": True, "default_branch": "main"},
                {"id": 1002, "full_name": "test_org/repo2", "private": False, "default_branch": "master"}
            ]
    def mock_init():
        return MockClient()
        
    # We patch the creation of the client when it's instantiated inside github.py and repositories.py
    monkeypatch.setattr("app.api.v1.github.GitHubAppClient", mock_init)
    monkeypatch.setattr("app.api.v1.repositories.GitHubAppClient", mock_init)
    
    res_avail = client.get(f"/api/v1/github/connections/{connection.id}/repositories")
    assert res_avail.status_code == 200
    avail_repos = res_avail.json()
    assert len(avail_repos) == 2
    assert avail_repos[0]["github_repo_id"] == 1001
    assert avail_repos[0]["already_added"] is False

    # 4. Add a repository
    res_add = client.post("/api/v1/repositories", json={
        "connection_id": str(connection.id),
        "github_repo_id": 1001
    })
    assert res_add.status_code == 200
    added_repo = res_add.json()
    assert added_repo["full_name"] == "test_org/repo1"
    assert added_repo["monitoring_enabled"] is False
    repo_id = added_repo["id"]

    # 5. List persisted repositories
    res_list = client.get("/api/v1/repositories")
    assert res_list.status_code == 200
    repos = res_list.json()
    assert len(repos) == 1
    assert repos[0]["id"] == repo_id
    
    # Also verify that list_available returns already_added=True now
    res_avail_after = client.get(f"/api/v1/github/connections/{connection.id}/repositories")
    assert res_avail_after.status_code == 200
    assert res_avail_after.json()[0]["already_added"] is True

    # 6. Toggle monitoring
    res_toggle = client.patch(f"/api/v1/repositories/{repo_id}", json={
        "monitoring_enabled": True
    })
    assert res_toggle.status_code == 200
    assert res_toggle.json()["monitoring_enabled"] is True


def test_repositories_ownership_protection(client, db_session, monkeypatch):
    """
    Verify that ownership is respected:
    Adding a repository via a connection owned by another user is rejected with 404.
    Toggling monitoring on another user's repository is rejected with 404.
    """
    client.post("/api/v1/auth/dev-login")
    # Current logged in dev user
    my_user = db_session.query(User).first()
    
    # Create another user
    other_user = User(email="other@example.com", auth_provider="github", external_auth_id="gh_999")
    db_session.add(other_user)
    db_session.commit()
    
    # Create connection for other user
    other_conn = GitHubConnection(
        user_id=other_user.id,
        installation_id=99999,
        account_login="other_org",
        account_type="Organization"
    )
    db_session.add(other_conn)
    db_session.commit()
    
    # Try to list available repositories for other user's connection
    res_avail = client.get(f"/api/v1/github/connections/{other_conn.id}/repositories")
    assert res_avail.status_code == 404
    
    # Try to add repository using other user's connection
    class MockClient:
        async def list_installation_repositories(self):
            return [{"id": 2001, "full_name": "other_org/repo1", "private": True, "default_branch": "main"}]
    def mock_init():
        return MockClient()
        
    monkeypatch.setattr("app.api.v1.repositories.GitHubAppClient", mock_init)
    
    res_add = client.post("/api/v1/repositories", json={
        "connection_id": str(other_conn.id),
        "github_repo_id": 2001
    })
    assert res_add.status_code == 404
    
    # Now explicitly create a repository for the other user to test PATCH
    other_repo = Repository(
        connection_id=other_conn.id,
        github_repo_id=2001,
        full_name="other_org/repo1",
        private=True,
        default_branch="main",
        monitoring_enabled=False
    )
    db_session.add(other_repo)
    db_session.commit()
    
    # Try to toggle monitoring on this other user's repository
    res_toggle = client.patch(f"/api/v1/repositories/{other_repo.id}", json={"monitoring_enabled": True})
    assert res_toggle.status_code == 404
