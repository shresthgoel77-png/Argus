"""
Factory-layer tests for environment-gated auth provider selection.

These test the SECOND layer of defence — the runtime factory guard —
independent of the config-layer pydantic validators.
"""
import pytest
from app.auth.factory import get_auth_provider
from app.auth.development.adapter import DevelopmentAuthProvider


def test_factory_returns_dev_in_development(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_provider", "development")
    monkeypatch.setattr(settings, "app_env", "development")

    provider = get_auth_provider()
    assert isinstance(provider, DevelopmentAuthProvider)


def test_factory_returns_dev_in_test(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_provider", "development")
    monkeypatch.setattr(settings, "app_env", "test")

    provider = get_auth_provider()
    assert isinstance(provider, DevelopmentAuthProvider)


def test_factory_raises_on_dev_in_production(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_provider", "development")
    monkeypatch.setattr(settings, "app_env", "production")

    with pytest.raises(
        ValueError,
        match="DevelopmentAuthProvider must never be instantiated in production",
    ):
        get_auth_provider()


def test_factory_returns_clerk_adapter(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_provider", "clerk")
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "clerk_secret_key", type("S", (), {"get_secret_value": lambda s: "sk_live_test"})())
    monkeypatch.setattr(settings, "clerk_jwt_key", None)
    monkeypatch.setattr(settings, "clerk_authorized_parties", None)

    from app.auth.clerk.adapter import ClerkAuthAdapter
    provider = get_auth_provider()
    assert isinstance(provider, ClerkAuthAdapter)


def test_factory_clerk_missing_config_raises(monkeypatch):
    """Clerk adapter constructor enforces its own key requirement."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_provider", "clerk")
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "clerk_secret_key", None)
    monkeypatch.setattr(settings, "clerk_jwt_key", None)
    monkeypatch.setattr(settings, "clerk_authorized_parties", None)

    with pytest.raises(ValueError, match="Clerk verification requires"):
        get_auth_provider()


def test_factory_raises_on_unrecognized(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_provider", "unknown_provider_xyz")
    monkeypatch.setattr(settings, "app_env", "development")

    with pytest.raises(NotImplementedError, match="not implemented"):
        get_auth_provider()
