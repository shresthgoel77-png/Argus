import httpx
import pytest

from app.integrations.ai import get_provider
from app.integrations.ai.exceptions import (
    AIProviderRateLimitedError,
    AIProviderUnavailableError,
    InvalidAPIKeyError,
)
from app.integrations.ai.gemini_client import GeminiClient
from app.integrations.ai.gemini_provider import GeminiProvider


SECRET_KEY = "AIza-test-secret-that-must-not-leak"


def make_client(response=None, *, error=None):
    def handler(request):
        if error is not None:
            raise error
        return response

    transport = httpx.MockTransport(handler)
    return GeminiClient(http_client=httpx.Client(transport=transport))


def test_gemini_provider_is_registered():
    assert get_provider("gemini") is GeminiProvider


def test_valid_key_returns_without_exception():
    response = httpx.Response(200, json={"models": []})
    GeminiProvider(make_client(response=response)).validate_api_key(SECRET_KEY)


@pytest.mark.parametrize("status", [401, 403])
def test_invalid_key_maps_to_invalid_api_key(status):
    provider = GeminiProvider(
        make_client(response=httpx.Response(status, text="secret details"))
    )
    with pytest.raises(InvalidAPIKeyError) as caught:
        provider.validate_api_key(SECRET_KEY)
    assert SECRET_KEY not in str(caught.value)


def test_rate_limit_maps_to_rate_limited():
    provider = GeminiProvider(make_client(response=httpx.Response(429)))
    with pytest.raises(AIProviderRateLimitedError) as caught:
        provider.validate_api_key(SECRET_KEY)
    assert SECRET_KEY not in str(caught.value)


@pytest.mark.parametrize(
    "response",
    [httpx.Response(500), httpx.Response(503)],
)
def test_server_errors_map_to_unavailable(response):
    provider = GeminiProvider(make_client(response=response))
    with pytest.raises(AIProviderUnavailableError) as caught:
        provider.validate_api_key(SECRET_KEY)
    assert SECRET_KEY not in str(caught.value)


def test_timeout_maps_to_unavailable_without_key_leak():
    provider = GeminiProvider(
        make_client(error=httpx.ReadTimeout("request timed out"))
    )
    with pytest.raises(AIProviderUnavailableError) as caught:
        provider.validate_api_key(SECRET_KEY)
    assert SECRET_KEY not in str(caught.value)


def test_network_error_maps_to_unavailable_without_key_leak():
    provider = GeminiProvider(
        make_client(error=httpx.ConnectError("network unavailable"))
    )
    with pytest.raises(AIProviderUnavailableError) as caught:
        provider.validate_api_key(SECRET_KEY)
    assert SECRET_KEY not in str(caught.value)


def test_default_timeout_is_passed_to_request():
    class RecordingClient:
        def __init__(self):
            self.timeout = None

        def get(self, url, *, headers, timeout):
            self.timeout = timeout
            return httpx.Response(200)

    http_client = RecordingClient()
    GeminiProvider(GeminiClient(http_client=http_client)).validate_api_key(SECRET_KEY)

    assert http_client.timeout == 10.0
