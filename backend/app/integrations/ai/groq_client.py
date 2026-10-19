"""Small HTTP client for Groq's OpenAI-compatible API."""

from __future__ import annotations

import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.ai.exceptions import (
    AIProviderInvalidRequestError,
    AIProviderInvalidResponseError,
    AIProviderNetworkError,
    AIProviderRateLimitedError,
    AIProviderUnavailableError,
    InvalidAPIKeyError,
)

_BASE_URL = "https://api.groq.com/openai/v1"
_RETRYABLE = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 2
logger = get_logger(__name__)


class GroqClient:
    def __init__(self, *, api_key: str | None = None, timeout: float | None = None,
                 http_client: httpx.Client | None = None) -> None:
        self._api_key = api_key
        self._timeout = timeout or settings.ai_request_timeout_seconds
        self._http_client = http_client

    def _request(self, method: str, path: str, *, api_key: str | None = None,
                 json: dict | None = None) -> httpx.Response:
        key = api_key or self._api_key or ""
        try:
            if self._http_client:
                return self._http_client.request(method, f"{_BASE_URL}{path}",
                    headers={"Authorization": f"Bearer {key}"}, json=json, timeout=self._timeout)
            with httpx.Client(timeout=self._timeout) as client:
                return client.request(method, f"{_BASE_URL}{path}",
                    headers={"Authorization": f"Bearer {key}"}, json=json)
        except httpx.TimeoutException:
            raise AIProviderNetworkError("The Groq request timed out. Retry later.") from None
        except httpx.TransportError:
            raise AIProviderNetworkError("Could not reach Groq. Check the connection and retry.") from None
        except httpx.HTTPError:
            raise AIProviderNetworkError("The Groq request could not be completed. Retry later.") from None

    @staticmethod
    def _retry_delay(attempt: int, response: httpx.Response | None = None) -> float | None:
        retry_after = response.headers.get("retry-after") if response is not None else None
        delay = 0.0
        if retry_after:
            try:
                delay = float(retry_after)
            except ValueError:
                try:
                    retry_at = parsedate_to_datetime(retry_after)
                    if retry_at.tzinfo is None:
                        retry_at = retry_at.replace(tzinfo=timezone.utc)
                    delay = max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
                except (TypeError, ValueError, OverflowError):
                    delay = 0.0
        if retry_after and delay > settings.ai_retry_max_delay_seconds:
            return None
        if retry_after:
            return delay
        return min(settings.ai_retry_base_delay_seconds * (2 ** (attempt - 1)),
                   settings.ai_retry_max_delay_seconds) * random.uniform(0.8, 1.2)

    def validate_api_key(self, api_key: str) -> None:
        response = self._request("GET", "/models", api_key=api_key)
        self._raise_for_status(response, validation=True)
        try:
            if not isinstance(response.json().get("data"), list):
                raise TypeError
        except (TypeError, ValueError, AttributeError):
            raise AIProviderInvalidResponseError("Groq returned invalid model metadata.") from None

    def validate_model(self, api_key: str, model: str) -> None:
        response = self._request("GET", "/models", api_key=api_key)
        self._raise_for_status(response, validation=True)
        try:
            models = response.json()["data"]
            available = {item.get("id") for item in models if isinstance(item, dict)}
        except (KeyError, TypeError, ValueError):
            raise AIProviderInvalidResponseError("Groq returned invalid model metadata.") from None
        if model not in available:
            raise AIProviderInvalidRequestError("The selected Groq model is unavailable to this API key.")

    def generate(self, *, model: str, system_instructions: str, content: str,
                 schema: dict, max_tokens: int) -> dict:
        from app.services.ai_generation_controls import (
            count_generation_attempt, current_connection_scope, observe_provider_quota,
        )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_instructions + "\nReturn only data matching the supplied JSON schema."},
                {"role": "user", "content": content},
            ],
            "max_completion_tokens": max_tokens,
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "application_response", "strict": False, "schema": schema,
            }},
        }
        response = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            count_generation_attempt()
            try:
                response = self._request("POST", "/chat/completions", json=payload)
            except AIProviderNetworkError:
                if attempt == _MAX_ATTEMPTS:
                    raise
                time.sleep(self._retry_delay(attempt) or 0)
                continue
            observe_provider_quota(
                "groq", model, current_connection_scope() or "unscoped", response.headers)
            if response.status_code not in _RETRYABLE or attempt == _MAX_ATTEMPTS:
                break
            delay = self._retry_delay(attempt, response)
            if delay is None:
                break
            time.sleep(delay)
        assert response is not None
        self._raise_for_status(response)
        try:
            return response.json()
        except (ValueError, TypeError):
            raise AIProviderInvalidResponseError("Groq returned malformed JSON.") from None

    @staticmethod
    def _raise_for_status(response: httpx.Response, *, validation: bool = False) -> None:
        if 200 <= response.status_code < 300:
            return
        status_code = response.status_code
        logger.warning("Groq request failed: status=%d", status_code)
        if status_code in (401, 403):
            raise InvalidAPIKeyError("Groq API key is invalid.")
        if status_code == 429:
            raise AIProviderRateLimitedError("Groq rate limited the request.")
        if status_code in (500, 502, 503, 504):
            raise AIProviderUnavailableError("Groq is temporarily unavailable.")
        if status_code == 408:
            raise AIProviderNetworkError("The Groq request timed out.")
        if validation and status_code == 400:
            raise InvalidAPIKeyError("Groq API key could not be validated.")
        raise AIProviderInvalidRequestError("Groq rejected the request or selected model.")
