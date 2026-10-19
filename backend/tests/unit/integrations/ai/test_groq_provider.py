import json

import httpx
import pytest

from app.bot.context_builder import BotContext
from app.bot.question_parser import BotIntent
from app.integrations.ai import get_provider
from app.integrations.ai.exceptions import (
    AIProviderInvalidRequestError,
    AIProviderInvalidResponseError,
    AIProviderRateLimitedError,
)
from app.integrations.ai.groq_client import GroqClient
from app.integrations.ai.groq_provider import GroqProvider
from app.services.ai_context_builder import FindingContext
from app.services.repository_summary_context_builder import RepositorySummaryContext


def test_groq_is_registered_and_supports_documented_schema_models():
    assert get_provider("groq") is GroqProvider
    assert {"openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"} <= set(
        GroqProvider.SUPPORTED_MODELS
    )


def test_groq_validates_key_model_and_generates_all_contracts():
    calls = []
    payload = {
        "summary": "A finding",
        "severity": "high",
        "confidence": 0.9,
        "recommendations": ["Review"],
    }
    def handler(request):
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "openai/gpt-oss-20b"}]})
        result = dict(payload)
        if '"key_insights"' in request.content.decode():
            result = {"summary": "Repository", "key_insights": ["CI failing"],
                      "recommendations": ["Fix CI"], "confidence": 0.8}
        if '"answer_text"' in request.content.decode():
            result = {"answer_text": "CI is failing.", "key_points": ["Build failed"],
                      "confidence": 0.8}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(result)}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = GroqProvider(GroqClient(api_key="mock-secret", http_client=client),
                            model="openai/gpt-oss-20b")
    provider.validate_api_key("mock-secret")
    provider.validate_model("mock-secret", "openai/gpt-oss-20b")
    finding = FindingContext("ci", "Build", "Explain the finding", "<evidence>failed</evidence>")
    summary = RepositorySummaryContext("owner/repo", "Summarize", "<evidence>CI failing</evidence>")
    bot = BotContext(BotIntent.ci_status, "Explain", "<evidence>build failed</evidence>", "test")

    assert provider.generate_analysis(finding).severity == "high"
    assert provider.generate_repository_summary(summary).key_insights == ["CI failing"]
    assert provider.generate_bot_response(bot).answer_text == "CI is failing."
    generation = [request for request in calls if request.method == "POST"]
    assert len(generation) == 3
    for request in generation:
        assert request.url.path.endswith("/chat/completions")
        sent = json.loads(request.content)
        assert sent["response_format"]["type"] == "json_schema"
        assert sent["model"] == "openai/gpt-oss-20b"
    client.close()


def test_groq_rejects_model_missing_from_account_catalog():
    client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"data": [{"id": "other-model"}]})
    ))
    provider = GroqProvider(GroqClient(api_key="mock", http_client=client))
    with pytest.raises(AIProviderInvalidRequestError, match="unavailable to this API key"):
        provider.validate_model("mock", "openai/gpt-oss-20b")
    client.close()


def test_groq_retries_retryable_response_and_counts_each_attempt(monkeypatch):
    attempts = []
    responses = iter([
        httpx.Response(503, headers={"Retry-After": "0"}),
        httpx.Response(200, json={"choices": [{"message": {"content":
            '{"answer_text":"ok","key_points":[],"confidence":0.5}'}}]}),
    ])
    monkeypatch.setattr("app.services.ai_generation_controls.count_generation_attempt",
                        lambda: attempts.append(1))
    monkeypatch.setattr("app.integrations.ai.groq_client.time.sleep", lambda _: None)
    client = GroqClient(api_key="mock", http_client=httpx.Client(
        transport=httpx.MockTransport(lambda request: next(responses))))
    result = client.generate(model="openai/gpt-oss-20b", system_instructions="safe",
        content="small", schema={"type": "object"}, max_tokens=100)
    assert len(attempts) == 2
    assert result["choices"]


def test_groq_rejects_malformed_output_without_leaking_payload():
    client = GroqProvider(client=type("Client", (), {"generate": lambda *args, **kwargs:
        {"choices": [{"message": {"content": "not-json"}}]}})())
    context = FindingContext("ci", "Build", "safe", "private evidence")
    with pytest.raises(AIProviderInvalidResponseError) as error:
        client.generate_analysis(context)
    assert "private evidence" not in str(error.value)


def test_groq_rate_limit_is_not_hidden_or_switched():
    http_client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(429, headers={"Retry-After": "60"})
    ))
    client = GroqClient(api_key="mock", http_client=http_client)
    with pytest.raises(AIProviderRateLimitedError):
        client.generate(model="openai/gpt-oss-20b", system_instructions="safe",
                        content="small", schema={"type": "object"}, max_tokens=30)
    http_client.close()


def test_groq_retries_network_timeout_with_bounded_attempt_count(monkeypatch):
    calls = []
    attempts = []
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("timeout", request=request)
    monkeypatch.setattr("app.services.ai_generation_controls.count_generation_attempt",
                        lambda: attempts.append(1))
    monkeypatch.setattr("app.integrations.ai.groq_client.time.sleep", lambda _: None)
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = GroqClient(api_key="mock", http_client=http_client)
    with pytest.raises(Exception, match="timed out"):
        client.generate(model="openai/gpt-oss-20b", system_instructions="safe",
                        content="small", schema={"type": "object"}, max_tokens=30)
    assert len(calls) == len(attempts) == 2
    http_client.close()
