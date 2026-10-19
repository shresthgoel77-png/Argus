"""Process-local quota, concurrency, deduplication, and result cache for AI calls."""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from collections import OrderedDict, deque
from concurrent.futures import Future
from typing import Callable, TypeVar

from app.core.config import settings
from app.integrations.ai.exceptions import AIProviderRateLimitedError
from app.models.ai_connection import AIConnection
from app.services.ai_context_common import bounded_generation_content

T = TypeVar("T")
_lock = threading.RLock()
_cache: OrderedDict[str, tuple[float, object]] = OrderedDict()
_inflight: dict[str, Future] = {}
_windows: dict[str, deque[float]] = {}
_user_semaphores: dict[str, threading.BoundedSemaphore] = {}
_global_semaphore = threading.BoundedSemaphore(settings.ai_global_concurrency)
_attempt_context = threading.local()
_provider_cooldowns: dict[str, tuple[float, float]] = {}
_CACHE_VERSION = "ai-cache-v1"


def _consume(scope: str, limit: int) -> None:
    now = time.monotonic()
    with _lock:
        window = _windows.setdefault(scope, deque())
        while window and now - window[0] >= 60:
            window.popleft()
        if len(window) >= limit:
            raise AIProviderRateLimitedError("The configured AI request budget was reached.")
        window.append(now)


def count_generation_attempt() -> None:
    """Called immediately before each provider generation HTTP attempt, including retries."""
    identity = getattr(_attempt_context, "identity", None)
    if identity is None:
        return
    user_id, provider, model, connection_id = identity
    quota_scope = f"{provider}:{model}:{connection_id}"
    with _lock:
        cooldown = _provider_cooldowns.get(quota_scope)
    if cooldown and cooldown[0] > time.monotonic() and cooldown[1] <= 0:
        raise AIProviderRateLimitedError("The provider reported an exhausted quota window.")
    _consume("global", settings.ai_global_requests_per_minute)
    _consume(f"user:{user_id}", settings.ai_user_requests_per_minute)
    _consume(f"provider-model:{quota_scope}", settings.ai_provider_model_requests_per_minute)


def current_connection_scope() -> str | None:
    identity = getattr(_attempt_context, "identity", None)
    return identity[3] if identity else None


def observe_provider_quota(provider: str, model: str, connection_id: str, headers) -> None:
    """Use documented rate-limit headers to pause requests when quota reaches zero."""
    remaining = {}
    for kind in ("requests", "tokens"):
        try:
            remaining[kind] = float(headers.get(f"x-ratelimit-remaining-{kind}", ""))
        except (TypeError, ValueError):
            pass
    exhausted = [kind for kind, count in remaining.items() if count <= 0]
    if not exhausted:
        return
    reset_seconds = 0.0
    for kind in exhausted:
        value = headers.get(f"x-ratelimit-reset-{kind}")
        if not value:
            continue
        try:
            if value.endswith("ms"):
                reset_seconds = max(reset_seconds, float(value[:-2]) / 1000)
            elif value.endswith("s") and not re.fullmatch(r"[0-9.]+s", value):
                total = 0.0
                matches = list(re.finditer(r"([0-9.]+)(ms|m|s)", value))
                if not matches or "".join(match.group(0) for match in matches) != value:
                    continue
                for match in matches:
                    amount = float(match.group(1))
                    total += amount / 1000 if match.group(2) == "ms" else amount * (60 if match.group(2) == "m" else 1)
                reset_seconds = max(reset_seconds, total)
            elif value.endswith("s"):
                reset_seconds = max(reset_seconds, float(value[:-1]))
            elif value.endswith("m"):
                reset_seconds = max(reset_seconds, float(value[:-1]) * 60)
            else:
                reset_seconds = max(reset_seconds, float(value))
        except ValueError:
            continue
    with _lock:
        _provider_cooldowns[f"{provider}:{model}:{connection_id}"] = (
            time.monotonic() + max(0, reset_seconds), 0.0)


def run_generation(*, user_id, repository_id, connection: AIConnection, feature: str,
                   system_instructions: str, content: str, parameters: dict,
                   generate: Callable[[], T]) -> T:
    """Run a successful-result-only cached/deduplicated provider call."""
    bounded = bounded_generation_content(content)
    revision = f"{connection.id}:{connection.updated_at.isoformat() if connection.updated_at else ''}:" + hashlib.sha256(
        connection.encrypted_api_key.encode()).hexdigest()
    digest = hashlib.sha256(json.dumps({
        "system": system_instructions,
        "content": bounded,
        "parameters": parameters,
    }, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
    cache_key = hashlib.sha256("|".join((
        _CACHE_VERSION, str(user_id), str(repository_id), revision,
        connection.provider, connection.model, feature, digest,
    )).encode()).hexdigest()

    now = time.monotonic()
    with _lock:
        cached = _cache.get(cache_key)
        if cached and cached[0] > now:
            _cache.move_to_end(cache_key)
            return cached[1].model_copy(deep=True) if hasattr(cached[1], "model_copy") else cached[1]
        if cached:
            del _cache[cache_key]
        future = _inflight.get(cache_key)
        owner = future is None
        if owner:
            future = Future()
            _inflight[cache_key] = future

    if not owner:
        result = future.result()
        return result.model_copy(deep=True) if hasattr(result, "model_copy") else result

    user_scope = str(user_id)
    with _lock:
        user_semaphore = _user_semaphores.setdefault(
            user_scope, threading.BoundedSemaphore(settings.ai_user_concurrency))
    if not _global_semaphore.acquire(blocking=False):
        with _lock:
            _inflight.pop(cache_key, None)
        future.set_exception(AIProviderRateLimitedError("AI generation concurrency budget is full."))
        raise AIProviderRateLimitedError("AI generation concurrency budget is full.")
    if not user_semaphore.acquire(blocking=False):
        _global_semaphore.release()
        with _lock:
            _inflight.pop(cache_key, None)
        future.set_exception(AIProviderRateLimitedError("AI generation concurrency budget is full."))
        raise AIProviderRateLimitedError("AI generation concurrency budget is full.")

    previous_identity = getattr(_attempt_context, "identity", None)
    _attempt_context.identity = (
        user_scope, connection.provider, connection.model, str(connection.id))
    try:
        result = generate()
        future.set_result(result)
        ttl = settings.ai_cache_ttl_seconds
        if ttl:
            with _lock:
                _cache[cache_key] = (time.monotonic() + ttl, result.model_copy(deep=True)
                                     if hasattr(result, "model_copy") else result)
                _cache.move_to_end(cache_key)
                while len(_cache) > settings.ai_cache_max_entries:
                    _cache.popitem(last=False)
        return result
    except BaseException as error:
        future.set_exception(error)
        raise
    finally:
        _attempt_context.identity = previous_identity
        user_semaphore.release()
        _global_semaphore.release()
        with _lock:
            _inflight.pop(cache_key, None)


def clear_process_state() -> None:
    """Test helper; production cache state is intentionally process-local."""
    with _lock:
        _cache.clear()
        _inflight.clear()
        _windows.clear()
        _provider_cooldowns.clear()
