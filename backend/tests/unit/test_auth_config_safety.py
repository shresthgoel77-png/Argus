import pytest
from pydantic import ValidationError
from app.core.config import Settings

def test_settings_development_auth(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_PROVIDER", "development")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    
    settings = Settings(_env_file=None)
    assert settings.app_env == "development"
    assert settings.auth_provider == "development"

def test_settings_test_env_auth(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AUTH_PROVIDER", "development")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    
    settings = Settings(_env_file=None)
    assert settings.app_env == "test"
    assert settings.auth_provider == "development"

def test_settings_production_auth_safety(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_PROVIDER", "development")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    
    with pytest.raises(ValueError) as exc_info:
        Settings(_env_file=None)
    
    assert "Development auth provider cannot be used in production environment" in str(exc_info.value)
