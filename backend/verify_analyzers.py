import asyncio
import uuid
import sys
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.models.repository import Repository
from app.models.github_connection import GitHubConnection

def test_manual_trigger():
    print("Testing manual-trigger endpoint with all 7 analyzers")
    with TestClient(app) as client:
        db = SessionLocal()
        try:
            # Setup a test user and repo
            user_id = str(uuid.uuid4())
            user = User(
                id=user_id,
                email="test_all_analyzers@example.com",
                clerk_id="test_clk_123",
                is_active=True
            )
            db.add(user)
            db.commit()

            installation = GitHubConnection(id=999, owner_id=user_id, status="active", installation_id=12345)
            db.add(installation)
            db.commit()

            repo_id = str(uuid.uuid4())
            repo = Repository(
                id=repo_id,
                owner_id=user_id,
                name="test-repo",
                full_name="test/test-repo",
                is_monitored=True,
                default_branch="main"
            )
            db.add(repo)
            db.commit()

            # Override the dependency user
            app.dependency_overrides.clear()
            from app.auth.dependencies import get_current_user
            def override_get_user():
                return user
            app.dependency_overrides[get_current_user] = override_get_user

            analyzers = [
                "ci",
                "pull_request",
                "issues",
                "repository_activity",
                "dependency",
                "security",
                "code_quality"
            ]

            success = True
            for analyzer_key in analyzers:
                print(f"Invoking {analyzer_key}...")
                resp = client.post(
                    f"/api/v1/repositories/{repo_id}/monitor-runs",
                    json={"analyzer_key": analyzer_key}
                )
                if resp.status_code == 200:
                    print(f"  Success! OK 200")
                else:
                    print(f"  Failed! {resp.status_code}: {resp.text}")
                    success = False

            if success:
                print("\nAll 7 analyzers triggered successfully!")
                return 0
            else:
                print("\nSome analyzers failed.")
                return 1

        finally:
            db.rollback()
            db.close()

if __name__ == "__main__":
    sys.exit(test_manual_trigger())
