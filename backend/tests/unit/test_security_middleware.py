from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.rate_limit import ApiRateLimitMiddleware
from app.main import app


def test_cors_allows_configured_frontend_and_omits_unexpected_origin():
    client = TestClient(app)

    allowed = client.get(
        "/", headers={"Origin": "http://localhost:3000"}
    )
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"

    rejected = client.get("/", headers={"Origin": "https://unexpected.example"})
    assert "access-control-allow-origin" not in rejected.headers


def test_api_rate_limit_returns_429_and_retry_after():
    limited_app = FastAPI()
    limited_app.add_middleware(
        ApiRateLimitMiddleware, max_requests=2, window_seconds=60
    )

    @limited_app.get("/api/v1/resource")
    def resource():
        return {"ok": True}

    client = TestClient(limited_app)
    assert client.get("/api/v1/resource").status_code == 200
    assert client.get("/api/v1/resource").status_code == 200

    limited = client.get("/api/v1/resource")
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limit_exceeded"
    assert int(limited.headers["retry-after"]) > 0


def test_production_requires_explicit_non_wildcard_cors_origins(monkeypatch):
    from app.core.config import Settings

    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    required = {
        "_env_file": None,
        "app_env": "production",
        "auth_provider": "clerk",
        "database_url": "sqlite:///test.db",
        "github_app_id": "123",
        "github_app_slug": "test",
        "github_app_private_key": "test-key",
        "github_app_webhook_secret": "test-secret",
        "ai_credential_encryption_key": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
        "session_secret_key": "production-session-key",
        "scheduler_shared_secret": "scheduler-secret",
        "clerk_secret_key": "clerk-secret",
        "clerk_authorized_parties": ["https://app.example.com"],
    }

    try:
        Settings(**required)
    except ValueError as exc:
        assert "CORS_ORIGINS must be explicitly configured" in str(exc)
    else:
        raise AssertionError("Production settings accepted implicit CORS origins")

    try:
        Settings(**required, cors_origins=["*"])
    except ValueError as exc:
        assert "explicit origins" in str(exc)
    else:
        raise AssertionError("Production settings accepted wildcard CORS origins")

    wildcard_parties = {
        **required,
        "cors_origins": ["https://app.example.com"],
        "clerk_authorized_parties": ["*"],
    }
    try:
        Settings(**wildcard_parties)
    except ValueError as exc:
        assert "CLERK_AUTHORIZED_PARTIES must contain explicit origins" in str(exc)
    else:
        raise AssertionError("Production settings accepted wildcard Clerk parties")