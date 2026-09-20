import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.auth.dependencies import get_current_user
from app.db.session import get_db

# Override dependencies so we don't need real db or real user auth
def override_get_current_user():
    class DummyUser:
        id = uuid.uuid4()
    return DummyUser()

class DummySnapshot:
    def __init__(self):
        self.overall_score = 90
        self.category_scores = {"security": 90}

class DummyFindingCount:
    pass

class DummyQuery:
    def filter(self, *args, **kwargs): return self
    def order_by(self, *args, **kwargs): return self
    def group_by(self, *args, **kwargs): return self
    def all(self): return []

class DummyDB:
    def query(self, *args):
        return DummyQuery()

def override_get_db():
    yield DummyDB()

app.dependency_overrides[get_current_user] = override_get_current_user
app.dependency_overrides[get_db] = override_get_db

# Also we need to bypass get_repository_or_404
from app.api.v1 import repositories
repositories.get_repository_or_404 = lambda db, user_id, repository_id: True

client = TestClient(app)

repo_id = str(uuid.uuid4())
response = client.get(f"/api/v1/repositories/{repo_id}/trends?window_days=30")
print(f"Status: {response.status_code}")
print(f"Body: {response.json()}")
