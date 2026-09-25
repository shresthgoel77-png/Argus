"""
Config-layer tests for environment-gated auth provider selection.

Proves the pydantic model_validator enforces:
1. production + development auth → ValueError
2. production + clerk + valid config → OK
3. development/test + development → OK
4. production + clerk + missing config → ValueError (fail-closed)
"""
import pytest
from pydantic import ValidationError
from app.core.config import Settings

# Shared base env kwargs that satisfy all non-auth validators
_BASE = dict(
    _env_file=None,
    database_url="sqlite:///test.db",
    github_app_id="123",
    github_app_slug="test",
    github_app_private_key="test-key",
    github_app_webhook_secret="test-secret",
    ai_credential_encryption_key="MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
)

# Extra fields required only in production
_PROD_EXTRAS = dict(
    session_secret_key="prod_secret_override",
    scheduler_shared_secret="sched_secret",
)


# ── Scenario 1: production + development auth → reject ──


def test_production_rejects_development_auth(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    with pytest.raises((ValueError, ValidationError), match="Development auth provider"):
        Settings(
            app_env="production",
            auth_provider="development",
            **_BASE,
            **_PROD_EXTRAS,
        )


# ── Scenario 2: production + clerk + valid config → accept ──


def test_production_accepts_clerk_with_secret_key(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    s = Settings(
        app_env="production",
        auth_provider="clerk",
        clerk_secret_key="sk_live_test123",
        **_BASE,
        **_PROD_EXTRAS,
    )
    assert s.auth_provider == "clerk"
    assert s.app_env == "production"


def test_production_accepts_clerk_with_jwt_key(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    s = Settings(
        app_env="production",
        auth_provider="clerk",
        clerk_jwt_key="-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----",
        **_BASE,
        **_PROD_EXTRAS,
    )
    assert s.auth_provider == "clerk"


# ── Scenario 3: development/test + development → accept ──


def test_development_env_allows_development_auth(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    s = Settings(app_env="development", auth_provider="development", **_BASE)
    assert s.app_env == "development"
    assert s.auth_provider == "development"


def test_test_env_allows_development_auth(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    s = Settings(app_env="test", auth_provider="development", **_BASE)
    assert s.app_env == "test"
    assert s.auth_provider == "development"


# ── Scenario 4: production + clerk + missing config → fail-closed ──


def test_production_clerk_without_keys_fails_closed(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    with pytest.raises(
        (ValueError, ValidationError),
        match="Clerk auth requires CLERK_SECRET_KEY or CLERK_JWT_KEY",
    ):
        Settings(
            app_env="production",
            auth_provider="clerk",
            # deliberately no clerk_secret_key / clerk_jwt_key
            **_BASE,
            **_PROD_EXTRAS,
        )


# ── Edge: unrecognised auth_provider value rejected at type level ──


def test_unrecognised_auth_provider_rejected(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    with pytest.raises((ValueError, ValidationError)):
        Settings(app_env="development", auth_provider="oauth2", **_BASE)
