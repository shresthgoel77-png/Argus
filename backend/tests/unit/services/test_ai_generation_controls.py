import threading
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import BaseModel

from app.integrations.ai.exceptions import AIProviderRateLimitedError
from app.services import ai_generation_controls as controls
from app.services.ai_context_common import bounded_generation_content


class Result(BaseModel):
    answer: str


def connection(*, model="model-a", revision="1"):
    return SimpleNamespace(
        id=uuid4(),
        updated_at=datetime(2026, 1, int(revision), tzinfo=timezone.utc),
        encrypted_api_key=f"ciphertext-{revision}",
        provider="groq",
        model=model,
    )


def run(conn, generate, *, user="user-a", repo="repo-a", content="same", feature="summary-v1"):
    return controls.run_generation(
        user_id=user, repository_id=repo, connection=conn, feature=feature,
        system_instructions="trusted", content=content, parameters={"schema": "v1"},
        generate=generate,
    )


@pytest.fixture(autouse=True)
def clean_state():
    controls.clear_process_state()
    controls._user_semaphores.clear()
    yield
    controls.clear_process_state()
    controls._user_semaphores.clear()
    controls._global_semaphore = threading.BoundedSemaphore(
        controls.settings.ai_global_concurrency)


def test_successes_are_cached_with_user_repository_input_and_connection_isolation():
    conn = connection()
    calls = []
    first = run(conn, lambda: calls.append(1) or Result(answer="safe"))
    second = run(conn, lambda: calls.append(2) or Result(answer="wrong"))
    assert first.answer == second.answer == "safe"
    assert len(calls) == 1

    run(conn, lambda: calls.append(3) or Result(answer="user"), user="user-b")
    run(conn, lambda: calls.append(4) or Result(answer="repo"), repo="repo-b")
    run(conn, lambda: calls.append(5) or Result(answer="input"), content="changed")
    run(connection(model="model-b"), lambda: calls.append(6) or Result(answer="model"))
    run(connection(revision="2"), lambda: calls.append(7) or Result(answer="revision"))
    assert len(calls) == 6


def test_failures_are_not_cached():
    conn = connection()
    calls = []
    def fail():
        calls.append(1)
        raise RuntimeError("provider unavailable")
    with pytest.raises(RuntimeError):
        run(conn, fail)
    assert run(conn, lambda: calls.append(2) or Result(answer="recovered")).answer == "recovered"
    assert calls == [1, 2]


def test_success_cache_expires_after_configured_ttl(monkeypatch):
    monkeypatch.setattr(controls.settings, "ai_cache_ttl_seconds", 1)
    clock = [0.0]
    monkeypatch.setattr(controls.time, "monotonic", lambda: clock[0])
    calls = []
    conn = connection()
    run(conn, lambda: calls.append(1) or Result(answer="first"))
    clock[0] = 2.0
    run(conn, lambda: calls.append(2) or Result(answer="second"))
    assert calls == [1, 2]


def test_context_budget_keeps_both_edges(monkeypatch):
    monkeypatch.setattr(controls.settings, "ai_max_input_chars", 1001)
    bounded = bounded_generation_content("A" * 1200 + "Z" * 1200)
    assert len(bounded) <= 1001
    assert bounded.startswith("A")
    assert bounded.endswith("Z")
    assert "middle context omitted" in bounded


def test_simultaneous_identical_calls_are_deduplicated():
    conn = connection()
    entered = threading.Event()
    release = threading.Event()
    calls = []
    results = []
    def generate():
        calls.append(1)
        entered.set()
        assert release.wait(2)
        return Result(answer="shared")
    worker = threading.Thread(target=lambda: results.append(run(conn, generate)))
    worker.start()
    assert entered.wait(2)
    second = threading.Thread(target=lambda: results.append(run(conn, generate)))
    second.start()
    release.set()
    worker.join(2)
    second.join(2)
    assert len(calls) == 1
    assert [result.answer for result in results] == ["shared", "shared"]


@pytest.mark.parametrize("scope", ["global", "user"])
def test_concurrency_budgets_reject_a_distinct_call_when_full(scope, monkeypatch):
    controls._user_semaphores.clear()
    if scope == "global":
        controls._global_semaphore = threading.BoundedSemaphore(1)
        monkeypatch.setattr(controls.settings, "ai_user_concurrency", 2)
    else:
        controls._global_semaphore = threading.BoundedSemaphore(2)
        monkeypatch.setattr(controls.settings, "ai_user_concurrency", 1)
    conn = connection()
    entered = threading.Event()
    release = threading.Event()
    worker = threading.Thread(target=lambda: run(conn, lambda: (
        entered.set(), release.wait(2), Result(answer="first"))[2]))
    worker.start()
    assert entered.wait(2)
    with pytest.raises(AIProviderRateLimitedError, match="concurrency budget"):
        run(conn, lambda: Result(answer="second"), repo="different-repository")
    release.set()
    worker.join(2)
    assert not worker.is_alive()


def test_generation_attempts_count_against_user_global_and_provider_model_limits(monkeypatch):
    monkeypatch.setattr(controls.settings, "ai_global_requests_per_minute", 20)
    monkeypatch.setattr(controls.settings, "ai_user_requests_per_minute", 1)
    monkeypatch.setattr(controls.settings, "ai_provider_model_requests_per_minute", 20)
    conn = connection()
    def two_attempts():
        controls.count_generation_attempt()
        controls.count_generation_attempt()
        return Result(answer="unused")
    with pytest.raises(AIProviderRateLimitedError):
        run(conn, two_attempts)


def test_provider_quota_headers_pause_model_until_reset(monkeypatch):
    monkeypatch.setattr(controls.time, "monotonic", lambda: 10.0)
    controls.observe_provider_quota("groq", "model-a", "connection-a", {
        "x-ratelimit-remaining-tokens": "0",
        "x-ratelimit-reset-tokens": "2m59.5s",
    })
    with pytest.raises(AIProviderRateLimitedError):
        controls._provider_cooldowns["groq:model-a:connection-a"] = (100.0, 0.0)
        controls._attempt_context.identity = ("user-a", "groq", "model-a", "connection-a")
        controls.count_generation_attempt()
    controls._attempt_context.identity = None
