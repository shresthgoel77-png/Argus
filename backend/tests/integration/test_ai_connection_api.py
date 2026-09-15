import pytest

from app.integrations.ai.exceptions import (
    AIProviderRateLimitedError,
    AIProviderUnavailableError,
    InvalidAPIKeyError,
    UnknownProviderError,
)
from app.services import ai_connection_service


class MockProvider:
    SUPPORTED_MODELS = ["supported-model"]

    def __init__(self, validation_error=None):
        self.validation_error = validation_error

    def validate_api_key(self, api_key):
        if self.validation_error:
            raise self.validation_error


def provider_class(provider):
    class Provider:
        SUPPORTED_MODELS = provider.SUPPORTED_MODELS

        def validate_api_key(self, api_key):
            return provider.validate_api_key(api_key)

    return Provider


def assert_key_not_in_response(response, api_key):
    assert api_key not in response.text


@pytest.mark.asyncio
async def test_create_connection_returns_safe_status(
    authorized_client, monkeypatch
):
    api_key = "valid-key-that-must-not-leak"
    monkeypatch.setattr(
        ai_connection_service,
        "get_provider",
        lambda _: provider_class(MockProvider()),
    )

    response = await authorized_client.post(
        "/api/v1/ai/connection",
        json={
            "provider": "mock",
            "model": "supported-model",
            "api_key": api_key,
        },
    )

    assert response.status_code == 201
    assert response.json()["configured"] is True
    assert response.json()["provider"] == "mock"
    assert response.json()["model"] == "supported-model"
    assert "api_key" not in response.json()
    assert_key_not_in_response(response, api_key)


@pytest.mark.asyncio
async def test_invalid_api_key_is_sanitized(
    authorized_client, monkeypatch
):
    api_key = "invalid-key-that-must-not-leak"
    monkeypatch.setattr(
        ai_connection_service,
        "get_provider",
        lambda _: provider_class(MockProvider(InvalidAPIKeyError(api_key))),
    )

    response = await authorized_client.post(
        "/api/v1/ai/connection",
        json={
            "provider": "mock",
            "model": "supported-model",
            "api_key": api_key,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "The provided API key could not be validated."
    assert_key_not_in_response(response, api_key)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_error", "expected_status", "expected_detail"),
    [
        (
            AIProviderRateLimitedError("rate-limit-key-fragment"),
            429,
            "The AI provider is rate limited. Please try again later.",
        ),
        (
            AIProviderUnavailableError("unavailable-key-fragment"),
            503,
            "The AI provider is currently unavailable. Please try again later.",
        ),
    ],
)
async def test_provider_errors_are_sanitized(
    authorized_client,
    monkeypatch,
    provider_error,
    expected_status,
    expected_detail,
):
    api_key = "provider-error-key-that-must-not-leak"
    monkeypatch.setattr(
        ai_connection_service,
        "get_provider",
        lambda _: provider_class(MockProvider(provider_error)),
    )

    response = await authorized_client.post(
        "/api/v1/ai/connection",
        json={
            "provider": "mock",
            "model": "supported-model",
            "api_key": api_key,
        },
    )

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail
    assert_key_not_in_response(response, api_key)
    assert_key_not_in_response(response, str(provider_error))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_setup", "model", "expected_detail"),
    [
        (
            lambda _: (_ for _ in ()).throw(
                UnknownProviderError("unknown-key-fragment")
            ),
            "supported-model",
            "The selected AI provider or model is not supported.",
        ),
        (
            lambda _: provider_class(MockProvider()),
            "unsupported-model",
            "The selected AI provider or model is not supported.",
        ),
    ],
)
async def test_unsupported_provider_or_model_is_sanitized(
    authorized_client,
    monkeypatch,
    provider_setup,
    model,
    expected_detail,
):
    api_key = "unsupported-key-that-must-not-leak"
    monkeypatch.setattr(ai_connection_service, "get_provider", provider_setup)

    response = await authorized_client.post(
        "/api/v1/ai/connection",
        json={
            "provider": "unsupported-provider",
            "model": model,
            "api_key": api_key,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == expected_detail
    assert_key_not_in_response(response, api_key)
    assert_key_not_in_response(response, "unknown-key-fragment")


@pytest.mark.asyncio
async def test_get_unconfigured_connection_returns_false(
    authorized_client,
):
    response = await authorized_client.get("/api/v1/ai/connection")

    assert response.status_code == 200
    assert response.json() == {"configured": False}


@pytest.mark.asyncio
async def test_get_configured_connection_returns_safe_status(
    authorized_client, monkeypatch
):
    api_key = "get-key-that-must-not-leak"
    monkeypatch.setattr(
        ai_connection_service,
        "get_provider",
        lambda _: provider_class(MockProvider()),
    )
    await authorized_client.post(
        "/api/v1/ai/connection",
        json={
            "provider": "mock",
            "model": "supported-model",
            "api_key": api_key,
        },
    )

    response = await authorized_client.get("/api/v1/ai/connection")

    assert response.status_code == 200
    assert response.json()["configured"] is True
    assert "api_key" not in response.json()
    assert_key_not_in_response(response, api_key)


@pytest.mark.asyncio
async def test_delete_connection_is_idempotent_and_has_no_body(
    authorized_client, monkeypatch
):
    api_key = "delete-key-that-must-not-leak"
    monkeypatch.setattr(
        ai_connection_service,
        "get_provider",
        lambda _: provider_class(MockProvider()),
    )
    await authorized_client.post(
        "/api/v1/ai/connection",
        json={
            "provider": "mock",
            "model": "supported-model",
            "api_key": api_key,
        },
    )

    first_delete = await authorized_client.delete("/api/v1/ai/connection")
    second_delete = await authorized_client.delete("/api/v1/ai/connection")

    assert first_delete.status_code == 204
    assert second_delete.status_code == 204
    assert first_delete.text == ""
    assert second_delete.text == ""
    assert_key_not_in_response(first_delete, api_key)
    assert_key_not_in_response(second_delete, api_key)
