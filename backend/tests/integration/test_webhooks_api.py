import pytest
import hmac
import hashlib
import json
from uuid import uuid4
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import get_db
from app.core.config import settings
from app.models.github_event import GitHubEvent
from app.models.github_connection import GitHubConnection
from app.models.user import User

@pytest.fixture
def unauth_client(db_session):
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

def _sign_payload(payload_bytes: bytes) -> str:
    secret_bytes = settings.github_app_webhook_secret.get_secret_value().encode('utf-8')
    mac = hmac.new(secret_bytes, payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={mac}"

def test_webhook_valid_new_delivery(unauth_client, db_session):
    payload = {"action": "created", "installation": {"id": 111}}
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = _sign_payload(body_bytes)
    delivery_id = str(uuid4())
    
    headers = {
        "x-github-event": "push",
        "x-github-delivery": delivery_id,
        "x-hub-signature-256": sig
    }
    
    resp = unauth_client.post("/api/v1/webhooks/github", content=body_bytes, headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    
    event = db_session.query(GitHubEvent).filter_by(delivery_id=delivery_id).first()
    assert event is not None
    assert event.status in ("processed", "ignored")

def test_webhook_valid_duplicate_delivery(unauth_client, db_session):
    payload = {"action": "created", "installation": {"id": 222}}
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = _sign_payload(body_bytes)
    delivery_id = str(uuid4())
    
    headers = {
        "x-github-event": "push",
        "x-github-delivery": delivery_id,
        "x-hub-signature-256": sig
    }
    
    resp1 = unauth_client.post("/api/v1/webhooks/github", content=body_bytes, headers=headers)
    assert resp1.status_code == 200
    
    resp2 = unauth_client.post("/api/v1/webhooks/github", content=body_bytes, headers=headers)
    assert resp2.status_code == 200
    
    events = db_session.query(GitHubEvent).filter_by(delivery_id=delivery_id).all()
    assert len(events) == 1

def test_webhook_invalid_missing_signature(unauth_client, db_session):
    payload = {"action": "created"}
    body_bytes = json.dumps(payload).encode("utf-8")
    delivery_id = str(uuid4())
    
    headers = {
        "x-github-event": "push",
        "x-github-delivery": delivery_id,
    }
    
    # Missing signature
    resp = unauth_client.post("/api/v1/webhooks/github", content=body_bytes, headers=headers)
    assert resp.status_code == 401
    
    # Invalid signature
    headers["x-hub-signature-256"] = "sha256=invalid"
    resp = unauth_client.post("/api/v1/webhooks/github", content=body_bytes, headers=headers)
    assert resp.status_code == 401
    
    events = db_session.query(GitHubEvent).filter_by(delivery_id=delivery_id).all()
    assert len(events) == 0

def test_webhook_missing_delivery_or_event(unauth_client):
    payload = {"action": "created"}
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = _sign_payload(body_bytes)
    
    headers = {
        "x-github-event": "push",
        "x-hub-signature-256": sig
    }
    
    resp = unauth_client.post("/api/v1/webhooks/github", content=body_bytes, headers=headers)
    assert resp.status_code == 400
    
    headers2 = {
        "x-github-delivery": str(uuid4()),
        "x-hub-signature-256": sig
    }
    resp = unauth_client.post("/api/v1/webhooks/github", content=body_bytes, headers=headers2)
    assert resp.status_code == 400

def test_webhook_malformed_json_valid_signature(unauth_client):
    body_bytes = b"not-json"
    sig = _sign_payload(body_bytes)
    delivery_id = str(uuid4())
    
    headers = {
        "x-github-event": "push",
        "x-github-delivery": delivery_id,
        "x-hub-signature-256": sig
    }
    
    resp = unauth_client.post("/api/v1/webhooks/github", content=body_bytes, headers=headers)
    assert resp.status_code == 400

def test_webhook_installation_suspend(unauth_client, db_session):
    # Seed user and connection
    user = User(email="suspend@example.com", auth_provider="github", external_auth_id="gh_suspend")
    db_session.add(user)
    db_session.commit()
    
    conn = GitHubConnection(
        user_id=user.id,
        installation_id=333,
        account_login="suspend_org",
        account_type="Organization",
        status="active"
    )
    db_session.add(conn)
    db_session.commit()
    
    payload = {"action": "suspend", "installation": {"id": 333}}
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = _sign_payload(body_bytes)
    delivery_id = str(uuid4())
    
    headers = {
        "x-github-event": "installation",
        "x-github-delivery": delivery_id,
        "x-hub-signature-256": sig
    }
    
    resp = unauth_client.post("/api/v1/webhooks/github", content=body_bytes, headers=headers)
    assert resp.status_code == 200
    
    db_session.refresh(conn)
    assert conn.status == "suspended"
    
    event = db_session.query(GitHubEvent).filter_by(delivery_id=delivery_id).first()
    assert event is not None
    assert event.status == "processed"

def test_webhook_installation_created(unauth_client, db_session):
    payload = {"action": "created", "installation": {"id": 444, "account": {"login": "new", "type": "User"}}}
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = _sign_payload(body_bytes)
    delivery_id = str(uuid4())
    
    headers = {
        "x-github-event": "installation",
        "x-github-delivery": delivery_id,
        "x-hub-signature-256": sig
    }
    
    resp = unauth_client.post("/api/v1/webhooks/github", content=body_bytes, headers=headers)
    assert resp.status_code == 200
    
    events = db_session.query(GitHubEvent).filter_by(delivery_id=delivery_id).all()
    assert len(events) == 1
    
    conns = db_session.query(GitHubConnection).filter_by(installation_id=444).all()
    assert len(conns) == 0
