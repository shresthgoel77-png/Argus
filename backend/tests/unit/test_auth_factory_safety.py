import pytest
from app.auth.factory import get_auth_provider
from app.auth.development.adapter import DevelopmentAuthProvider

def test_factory_returns_dev_in_non_prod(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_provider", "development")
    monkeypatch.setattr(settings, "app_env", "development")
    
    provider = get_auth_provider()
    assert isinstance(provider, DevelopmentAuthProvider)

def test_factory_raises_on_dev_in_production(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_provider", "development")
    monkeypatch.setattr(settings, "app_env", "production")
    
    with pytest.raises(ValueError, match="DevelopmentAuthProvider must never be instantiated in production"):
        get_auth_provider()


def test_factory_raises_on_unrecognized(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_provider", "unknown_provider_xyz")
    monkeypatch.setattr(settings, "app_env", "development")
    
    with pytest.raises(NotImplementedError, match="not implemented"):
        get_auth_provider()
