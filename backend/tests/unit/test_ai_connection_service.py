import pytest

from app.integrations.ai.exceptions import InvalidAPIKeyError
from app.models.ai_connection import AIConnection
from app.services import ai_connection_service


class MockProvider:
    SUPPORTED_MODELS = ["supported-model"]

    def __init__(self, validation_error=None):
        self.validation_error = validation_error
        self.calls = []

    def validate_api_key(self, api_key):
        self.calls.append(api_key)
        if self.validation_error:
            raise self.validation_error


def provider_class(provider):
    class Provider:
        SUPPORTED_MODELS = provider.SUPPORTED_MODELS

        def validate_api_key(self, api_key):
            return provider.validate_api_key(api_key)

    return Provider


def test_create_connection_validates_before_persisting(db_session, test_user, monkeypatch):
    provider = MockProvider(InvalidAPIKeyError("invalid"))
    monkeypatch.setattr(ai_connection_service, "get_provider", lambda _: provider_class(provider))

    with pytest.raises(InvalidAPIKeyError):
        ai_connection_service.create_or_replace_connection(
            db_session, test_user.id, "mock", "supported-model", "invalid-key"
        )

    assert db_session.query(AIConnection).filter(
        AIConnection.user_id == test_user.id
    ).first() is None
    assert provider.calls == ["invalid-key"]


def test_create_connection_rejects_unsupported_model_without_provider_call(
    db_session, test_user, monkeypatch
):
    provider = MockProvider()
    monkeypatch.setattr(ai_connection_service, "get_provider", lambda _: provider_class(provider))

    with pytest.raises(ValueError, match="not supported"):
        ai_connection_service.create_or_replace_connection(
            db_session, test_user.id, "mock", "unsupported-model", "valid-key"
        )

    assert provider.calls == []


def test_create_connection_replaces_existing_row_and_status_is_safe(
    db_session, test_user, monkeypatch
):
    provider = MockProvider()
    monkeypatch.setattr(ai_connection_service, "get_provider", lambda _: provider_class(provider))

    first = ai_connection_service.create_or_replace_connection(
        db_session, test_user.id, "mock", "supported-model", "first-key"
    )
    second = ai_connection_service.create_or_replace_connection(
        db_session, test_user.id, "mock", "supported-model", "second-key"
    )

    assert first.id == second.id
    assert db_session.query(AIConnection).filter(
        AIConnection.user_id == test_user.id
    ).count() == 1
    status = ai_connection_service.get_connection_status(db_session, test_user.id)
    assert set(status) == {"provider", "model", "status", "last_validated_at"}
    assert "first-key" not in status.values()
    assert "second-key" not in status.values()
    assert ai_connection_service.get_decrypted_api_key(db_session, test_user.id) == "second-key"


def test_delete_connection_is_idempotent(db_session, test_user, monkeypatch):
    monkeypatch.setattr(
        ai_connection_service,
        "get_provider",
        lambda _: provider_class(MockProvider()),
    )
    ai_connection_service.create_or_replace_connection(
        db_session, test_user.id, "mock", "supported-model", "valid-key"
    )

    ai_connection_service.delete_connection(db_session, test_user.id)
    ai_connection_service.delete_connection(db_session, test_user.id)

    assert ai_connection_service.get_connection_status(db_session, test_user.id) is None


def test_get_connection_status_returns_none_when_unconfigured(db_session, test_user):
    assert ai_connection_service.get_connection_status(db_session, test_user.id) is None