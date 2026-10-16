"""
Safety regression suite enforcing development authentication isolation.

This module guarantees against accidental exposure of development-only
authentication pathways in production environments, as required by Section 25
of the Master Blueprint.
"""
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.auth.factory import get_auth_provider
from app.auth.development.adapter import DevelopmentAuthProvider

# Shared base env kwargs to satisfy non-auth validators during simulation
_BASE_SIMULATION_ENV = dict(
    _env_file=None,
    database_url="sqlite:///test.db",
    github_app_id="123",
    github_app_slug="test",
    github_app_private_key="test-key",
    github_app_webhook_secret="test-secret",
    ai_credential_encryption_key="MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
    session_secret_key="prod_secret_override",
    scheduler_shared_secret="sched_secret",
    cors_origins=["https://app.example.com"],
    clerk_authorized_parties=["https://app.example.com"],
)

def test_development_auth_provider_is_test_only(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_provider", "development")
    monkeypatch.setattr(settings, "app_env", "development")

    with pytest.raises(ValueError, match="outside the test environment"):
        get_auth_provider()

    monkeypatch.setattr(settings, "app_env", "test")
    provider_test = get_auth_provider()
    assert isinstance(provider_test, DevelopmentAuthProvider)


def test_production_environment_rejects_development_adapter(monkeypatch):
    """
    Proves that a simulated production environment configuration cannot 
    select the development adapter under any tested variation.
    """
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    
    # 1. Direct configuration attempt via Pydantic model
    with pytest.raises((ValueError, ValidationError), match="auth_provider"):
        Settings(
            app_env="production",
            auth_provider="development",
            **_BASE_SIMULATION_ENV
        )

    # 2. Bypassing config layer directly at runtime factory
    from app.core.config import settings
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "auth_provider", "development")
    
    with pytest.raises(ValueError, match="outside the test environment"):
        get_auth_provider()


def test_invalid_production_config_fails_closed(monkeypatch):
    """
    Proves that an invalid/incomplete production authentication configuration 
    fails closed rather than degrading to development auth or bypassing requirements.
    """
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    
    # Missing required production keys (e.g. clerk keys when using Clerk auth)
    with pytest.raises((ValueError, ValidationError)):
        Settings(
            app_env="production",
            auth_provider="clerk",
            # Intentionally missing clerk_secret_key / clerk_jwt_key
            **_BASE_SIMULATION_ENV
        )

    # Missing auth_provider value completely / unrecognised
    with pytest.raises((ValueError, ValidationError)):
        Settings(
            app_env="production",
            auth_provider="unknown_provider_fallback",
            **_BASE_SIMULATION_ENV
        )
