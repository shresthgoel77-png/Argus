import os
import uuid
import json
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from fastapi.testclient import TestClient
from app.main import app
from app.db.base_class import Base
from app.db.session import engine, SessionLocal
from app.models.user import User
from app.models.repository import Repository
from app.models.repository_health_snapshot import RepositoryHealthSnapshot
from app.models.finding import Finding

# Determine where GitHubConnection is
try:
    from app.models.github_connection import GitHubConnection
except ImportError:
    # try another path if needed, usually it's there
    pass

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
engine_override = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
SessionLocal.configure(bind=engine_override)
Base.metadata.create_all(bind=engine_override)
db = SessionLocal()

# Setup Data
user_id = uuid.uuid4()
user = User(id=user_id, email="test@example.com", auth_provider="github", external_auth_id="123")
db.add(user)

conn_id = uuid.uuid4()
conn = GitHubConnection(id=conn_id, user_id=user_id, installation_id=1234, account_login="test", account_type="User")
db.add(conn)

repo_id = uuid.uuid4()
repo = Repository(id=repo_id, github_repo_id=999, full_name="test/test-repo", connection_id=conn_id)
db.add(repo)

now = datetime.utcnow()

s_100 = RepositoryHealthSnapshot(repository_id=repo_id, computed_at=now - timedelta(days=100), overall_score=30, category_scores={"security": 30})
s_90 = RepositoryHealthSnapshot(repository_id=repo_id, computed_at=now - timedelta(days=89), overall_score=50, category_scores={"security": 50})
s_30 = RepositoryHealthSnapshot(repository_id=repo_id, computed_at=now - timedelta(days=29), overall_score=70, category_scores={"security": 70})
s_0 = RepositoryHealthSnapshot(repository_id=repo_id, computed_at=now, overall_score=100, category_scores={"security": 100})
db.add_all([s_100, s_90, s_30, s_0])

db.commit()

# Mock Auth
from app.auth.dependencies import get_current_user
from app.db.session import get_db

app.dependency_overrides[get_current_user] = lambda: user
def override_get_db():
    yield db
app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

print("=========================")
print("--- Test 1: window_days=30 ---")
res = client.get(f"/api/v1/repositories/{repo_id}/trends?window_days=30")
print(res.status_code)
data_30 = res.json()
overall_delta_30 = data_30["health_trend"]["overall_delta"]
print(f"overall_delta: {overall_delta_30}")
assert overall_delta_30 == 30, f"Expected 30, got {overall_delta_30}"

print("--- Test 2: window_days=90 ---")
res = client.get(f"/api/v1/repositories/{repo_id}/trends?window_days=90")
print(res.status_code)
data_90 = res.json()
overall_delta_90 = data_90["health_trend"]["overall_delta"]
print(f"overall_delta: {overall_delta_90}")
assert overall_delta_90 == 50, f"Expected 50, got {overall_delta_90}"

print("--- Test 3: window_days=100 (capped check) ---")
res = client.get(f"/api/v1/repositories/{repo_id}/trends?window_days=100")
print(res.status_code)
assert res.status_code == 422, f"Expected 422, got {res.status_code}"

# Ownership scoping check
unowned_user_id = uuid.uuid4()
unowned_conn_id = uuid.uuid4()
unowned_conn = GitHubConnection(id=unowned_conn_id, user_id=unowned_user_id, installation_id=5678, account_login="other", account_type="User")
db.add(unowned_conn)

unowned_repo_id = uuid.uuid4()
unowned_repo = Repository(id=unowned_repo_id, github_repo_id=998, full_name="other/repo2", connection_id=unowned_conn_id)
db.add(unowned_repo)
db.commit()

print("--- Test 4: Ownership scoping ---")
res = client.get(f"/api/v1/repositories/{unowned_repo_id}/trends?window_days=30")
print(res.status_code)
assert res.status_code == 404, f"Expected 404, got {res.status_code}"

print("=========================")
print("All verifications passed!")
