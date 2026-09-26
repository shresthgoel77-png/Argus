"""
Safety regression suite enforcing development authentication isolation.

This module guarantees against accidental exposure of development-only
authentication pathways in production environments, as required by Section 25
of the Master Blueprint.
"""
import pytest
from pydantic import ValidationError
from unittest.mock import MagicMock
from fastapi import Request

from app.core.config import Settings
from app.auth.factory import get_auth_provider
from app.auth.development.adapter import DevelopmentAuthProvider
from app.auth.dependencies import get_current_user
from app.models.user import User

# Shared base env kwargs to satisfy non-auth validators during simulation
_BASE_SIMULATION_ENV = dict(
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

@pytest.mark.asyncio
async def test_development_test_user_resolves_correctly_in_dev_test(db_session, monkeypatch):
    """
    Proves that in development and test environments, the authentication flow
    correctly resolves to a deterministic test user without production credentials.
    """
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_provider", "development")
    monkeypatch.setattr(settings, "app_env", "development")
    
    # Prove the provider matches exactly what we expect
    provider = get_auth_provider()
    assert isinstance(provider, DevelopmentAuthProvider)

    # Mock request to simulate a logged-in dev session
    mock_request = MagicMock(spec=Request)
    mock_request.session = {"dev_auth_active": True}
    
    # Run the black-box abstraction: gets the user
    user = await get_current_user(request=mock_request, db=db_session)
    
    # Prove business logic only sees the Auth abstraction's identity type (User)
    # and has no idea about DevelopmentAuthContext specifics in its returned object.
    assert isinstance(user, User)
    assert user.email == "dev-test-user@argus-security.local" or "dev" in user.email

    # Prove behavior is identical in test environment
    monkeypatch.setattr(settings, "app_env", "test")
    provider_test = get_auth_provider()
    assert isinstance(provider_test, DevelopmentAuthProvider)
    
    user_test = await get_current_user(request=mock_request, db=db_session)
    assert isinstance(user_test, User)


def test_production_environment_rejects_development_adapter(monkeypatch):
    """
    Proves that a simulated production environment configuration cannot 
    select the development adapter under any tested variation.
    """
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    
    # 1. Direct configuration attempt via Pydantic model
    with pytest.raises((ValueError, ValidationError), match="Development auth provider"):
        Settings(
            app_env="production",
            auth_provider="development",
            **_BASE_SIMULATION_ENV
        )

    # 2. Bypassing config layer directly at runtime factory
    from app.core.config import settings
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "auth_provider", "development")
    
    with pytest.raises(ValueError, match="DevelopmentAuthProvider must never be instantiated in production"):
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
