import httpx
import pytest

from app.integrations.ai import get_provider
from app.integrations.ai.exceptions import (
    AIProviderInvalidResponseError,
    AIProviderRateLimitedError,
    AIProviderUnavailableError,
    InvalidAPIKeyError,
)
from app.integrations.ai.gemini_client import GeminiClient
from app.integrations.ai.gemini_provider import GeminiProvider
from app.services.ai_context_builder import FindingContext


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


class StubGenerationClient:
    def __init__(self, response=None, *, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def make_context():
    return FindingContext(
        category="security",
        title="Unsafe finding",
        system_instructions="<system_instructions>trusted</system_instructions>",
        untrusted_content="<untrusted_repository_content>data</untrusted_repository_content>",
    )


def make_generation_response(result):
    return {
        "candidates": [
            {"content": {"parts": [{"text": result}]}}
        ]
    }


def test_generate_analysis_returns_validated_result_and_preserves_boundaries():
    client = StubGenerationClient(
        make_generation_response(
            '{"summary":"Explain it","severity":"high",'
            '"confidence":0.8,"recommendations":["Fix it"]}'
        )
    )
    provider = GeminiProvider(client)

    result = provider.generate_analysis(make_context())

    assert result.summary == "Explain it"
    assert result.confidence == 0.8
    assert result.recommendations == ["Fix it"]
    assert client.calls == [
        {
            "model": GeminiProvider.DEFAULT_MODEL,
            "system_instructions": "<system_instructions>trusted</system_instructions>",
            "untrusted_content": "<untrusted_repository_content>data</untrusted_repository_content>",
        }
    ]


@pytest.mark.parametrize(
    "response",
    [
        make_generation_response("not-json"),
        make_generation_response('{"summary":"missing confidence"}'),
        make_generation_response(
            '{"summary":"bad confidence","severity":"high",'
            '"confidence":1.5,"recommendations":[]}'
        ),
    ],
)
def test_generate_analysis_rejects_invalid_structured_response(response):
    provider = GeminiProvider(StubGenerationClient(response))

    with pytest.raises(AIProviderInvalidResponseError):
        provider.generate_analysis(make_context())


@pytest.mark.parametrize(
    "error",
    [
        InvalidAPIKeyError("invalid"),
        AIProviderRateLimitedError("limited"),
        AIProviderUnavailableError("unavailable"),
    ],
)
def test_generate_analysis_preserves_mapped_transport_errors(error):
    provider = GeminiProvider(StubGenerationClient(error=error))

    with pytest.raises(type(error)):
        provider.generate_analysis(make_context())


@pytest.mark.parametrize("status", [401, 403])
def test_generation_invalid_key_maps_to_invalid_api_key(status):
    provider = GeminiProvider(make_client(response=httpx.Response(status)))

    with pytest.raises(InvalidAPIKeyError):
        provider.generate_analysis(make_context())


def test_generation_rate_limit_maps_to_rate_limited():
    provider = GeminiProvider(make_client(response=httpx.Response(429)))

    with pytest.raises(AIProviderRateLimitedError):
        provider.generate_analysis(make_context())


def test_generation_timeout_maps_to_unavailable():
    provider = GeminiProvider(make_client(error=httpx.ReadTimeout("request timed out")))

    with pytest.raises(AIProviderUnavailableError):
        provider.generate_analysis(make_context())
