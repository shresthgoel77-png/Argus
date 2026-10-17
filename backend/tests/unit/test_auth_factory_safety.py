"""
Factory-layer tests for environment-gated auth provider selection.

These test the SECOND layer of defence — the runtime factory guard —
independent of the config-layer pydantic validators.
"""
import pytest
from app.auth.factory import get_auth_provider
from app.auth.development.adapter import DevelopmentAuthProvider


def test_factory_rejects_dev_provider_outside_test(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_provider", "development")
    monkeypatch.setattr(settings, "app_env", "development")

    with pytest.raises(ValueError, match="outside the test environment"):
        get_auth_provider()


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
        match="outside the test environment",
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


def test_clerk_client_reused_and_configuration_changes_isolated(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from unittest.mock import MagicMock
    from pydantic import SecretStr
    from app.auth.factory import _get_clerk_provider
    from app.core.config import settings

    constructor = MagicMock()
    monkeypatch.setattr("app.auth.clerk.adapter.Clerk", constructor)
    monkeypatch.setattr(settings, "auth_provider", "clerk")
    monkeypatch.setattr(settings, "clerk_secret_key", SecretStr("sk_test_reuse"))
    monkeypatch.setattr(settings, "clerk_jwt_key", None)
    monkeypatch.setattr(settings, "clerk_authorized_parties", ["https://first.example"])
    _get_clerk_provider.cache_clear()
    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            providers = list(executor.map(lambda _: get_auth_provider(), range(8)))
        assert all(provider is providers[0] for provider in providers)
        assert constructor.call_count == 1
        for attribute, value in [
            ("clerk_secret_key", SecretStr("sk_test_rotated")),
            ("clerk_jwt_key", "rotated-jwt-key"),
            ("clerk_authorized_parties", ["https://second.example"]),
        ]:
            previous = get_auth_provider()
            monkeypatch.setattr(settings, attribute, value)
            assert get_auth_provider() is not previous
        assert constructor.call_count == 4
    finally:
        _get_clerk_provider.cache_clear()
