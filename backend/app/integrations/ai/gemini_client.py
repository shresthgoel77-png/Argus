"""Small raw HTTP client for Gemini validation and content generation."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import re
import random
import time

import httpx

from app.core.logging import get_logger
from app.core.config import settings
from app.integrations.ai.exceptions import (
    AIProviderInvalidRequestError,
    AIProviderInvalidResponseError,
    AIProviderNetworkError,
    AIProviderRateLimitedError,
    AIProviderUnavailableError,
    InvalidAPIKeyError,
)

_GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"
_DEFAULT_TIMEOUT_SECONDS = 20.0
_MAX_GENERATION_ATTEMPTS = 3
_RETRY_BASE_DELAY_SECONDS = 0.1
_RETRY_MAX_DELAY_SECONDS = 1.0
_TRANSIENT_SERVER_STATUSES = {500, 502, 503, 504}
_MAX_MODEL_METADATA_PAGES = 100
_GEMINI_GENERATE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)
_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "summary": {"type": "STRING"},
        "severity": {"type": "STRING"},
        "confidence": {"type": "NUMBER"},
        "reasoning_summary": {"type": "STRING"},
        "recommendations": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["summary", "severity", "confidence", "recommendations"],
}

logger = get_logger(__name__)


class GeminiClient:
    """Client for the side-effect-free Gemini models-list validation call."""

    def __init__(
        self,
        *,
        timeout: float | None = None,
        http_client: httpx.Client | None = None,
        api_key: str | None = None,
    ) -> None:
        self._timeout = timeout or settings.ai_request_timeout_seconds
        self._http_client = http_client
        self._api_key = api_key

    def validate_api_key(self, api_key: str) -> None:
        """Raise a provider exception unless *api_key* is accepted by Gemini."""
        try:
            if self._http_client is not None:
                response = self._http_client.get(
                    _GEMINI_MODELS_URL,
                    headers={"x-goog-api-key": api_key},
                    timeout=self._timeout,
                )
            else:
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.get(
                        _GEMINI_MODELS_URL,
                        headers={"x-goog-api-key": api_key},
                    )
        except httpx.TransportError:
            logger.warning(
                "Gemini key validation failed: status=network_error model=unselected request_id=unavailable attempt=1"
            )
            raise AIProviderNetworkError(
                "Could not reach Gemini to validate the API key. Check the connection and retry."
            ) from None
        except httpx.HTTPError:
            logger.warning(
                "Gemini key validation failed: status=request_error model=unselected request_id=unavailable attempt=1"
            )
            raise AIProviderNetworkError(
                "The Gemini API-key validation request could not be completed. Retry the request."
            ) from None

        if 200 <= response.status_code < 300:
            return
        self._log_response_failure(response, model="unselected")
        if response.status_code in (401, 403) or self._is_invalid_api_key(response):
            raise InvalidAPIKeyError("Gemini API key is invalid")
        if response.status_code == 429:
            raise AIProviderRateLimitedError("Gemini API rate limit exceeded")
        if response.status_code >= 500:
            raise AIProviderUnavailableError(
                "Gemini is temporarily unavailable while validating the API key. Retry later."
            )
        raise AIProviderInvalidRequestError(
            "Gemini rejected API-key validation. Check the key and retry."
        )

    def validate_model(self, api_key: str, model: str) -> None:
        """Check provider metadata for the selected model's generateContent support."""
        page_token: str | None = None
        seen_tokens: set[str] = set()

        for _ in range(_MAX_MODEL_METADATA_PAGES):
            params = {"pageToken": page_token} if page_token else None
            try:
                if self._http_client is not None:
                    response = self._http_client.get(
                        _GEMINI_MODELS_URL,
                        headers={"x-goog-api-key": api_key},
                        params=params,
                        timeout=self._timeout,
                    )
                else:
                    with httpx.Client(timeout=self._timeout) as client:
                        response = client.get(
                            _GEMINI_MODELS_URL,
                            headers={"x-goog-api-key": api_key},
                            params=params,
                        )
            except httpx.TransportError:
                logger.warning(
                    "Gemini model validation failed: status=network_error model=%s request_id=unavailable attempt=1",
                    model,
                )
                raise AIProviderNetworkError(
                    "Could not reach Gemini to validate model support. Check the connection and retry."
                ) from None
            except httpx.HTTPError:
                logger.warning(
                    "Gemini model validation failed: status=request_error model=%s request_id=unavailable attempt=1",
                    model,
                )
                raise AIProviderNetworkError(
                    "The Gemini model-support request could not be completed. Retry the request."
                ) from None

            if not 200 <= response.status_code < 300:
                self._log_response_failure(response, model=model)
            if response.status_code in (401, 403) or self._is_invalid_api_key(response):
                raise InvalidAPIKeyError("Gemini API key is invalid")
            if response.status_code == 429:
                raise AIProviderRateLimitedError(
                    "Gemini rate limited model validation. Please retry later."
                )
            if response.status_code >= 500:
                raise AIProviderUnavailableError(
                    "Gemini is temporarily unavailable while validating model support. Retry later."
                )
            if not 200 <= response.status_code < 300:
                raise AIProviderInvalidRequestError(
                    "Gemini rejected model validation. Check the selected model and API key."
                )

            try:
                payload = response.json()
                models = payload["models"]
                if not isinstance(models, list):
                    raise TypeError
            except (KeyError, TypeError, ValueError):
                raise AIProviderInvalidResponseError(
                    "Gemini returned invalid model metadata."
                ) from None

            for item in models:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                if name not in (model, f"models/{model}"):
                    continue
                methods = item.get("supportedGenerationMethods", [])
                if isinstance(methods, list) and "generateContent" in methods:
                    return
                raise AIProviderInvalidRequestError(
                    "The selected Gemini model does not support content generation."
                )

            next_token = payload.get("nextPageToken")
            if not next_token:
                raise AIProviderInvalidRequestError(
                    "The selected Gemini model is unavailable to this API key or does not support content generation."
                )
            if not isinstance(next_token, str) or next_token in seen_tokens:
                raise AIProviderInvalidResponseError(
                    "Gemini returned invalid model pagination metadata."
                )
            seen_tokens.add(next_token)
            page_token = next_token

        raise AIProviderInvalidResponseError(
            "Gemini model metadata exceeded the supported number of pages."
        )

    def generate_content(
        self,
        *,
        model: str,
        system_instructions: str,
        untrusted_content: str,
        response_schema: dict | None = None,
    ) -> dict:
        """Return Gemini's structured content response without exposing request data in errors."""
        url = _GEMINI_GENERATE_URL.format(model=model)
        schema = response_schema if response_schema is not None else _RESPONSE_SCHEMA
        payload = {
            "systemInstruction": {"parts": [{"text": system_instructions}]},
            "contents": [{"role": "user", "parts": [{"text": untrusted_content}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": schema,
                "maxOutputTokens": settings.ai_max_output_tokens,
            },
        }
        response: httpx.Response | None = None
        for attempt in range(1, _MAX_GENERATION_ATTEMPTS + 1):
            from app.services.ai_generation_controls import count_generation_attempt
            count_generation_attempt()
            try:
                if self._http_client is not None:
                    response = self._http_client.post(
                        url,
                        headers={"x-goog-api-key": self._api_key or ""},
                        json=payload,
                        timeout=self._timeout,
                    )
                else:
                    with httpx.Client(timeout=self._timeout) as client:
                        response = client.post(
                            url,
                            headers={"x-goog-api-key": self._api_key or ""},
                            json=payload,
                        )
            except httpx.TransportError:
                logger.warning(
                    "Gemini generation attempt failed: status=network_error model=%s request_id=unavailable attempt=%d",
                    model,
                    attempt,
                )
                if attempt < _MAX_GENERATION_ATTEMPTS:
                    time.sleep(self._retry_delay(attempt))
                    continue
                raise AIProviderNetworkError(
                    "Could not reach Gemini to generate content. Check the connection and retry."
                ) from None
            except httpx.HTTPError:
                raise AIProviderNetworkError(
                    "The Gemini generation request could not be completed. Check the connection and retry."
                ) from None

            if (
                response.status_code == 429
                or response.status_code in _TRANSIENT_SERVER_STATUSES
            ):
                request_id = self._request_id(response)
                logger.warning(
                    "Gemini generation attempt failed: status=%d model=%s request_id=%s attempt=%d",
                    response.status_code,
                    model,
                    request_id or "unavailable",
                    attempt,
                )
                if attempt < _MAX_GENERATION_ATTEMPTS:
                    delay = self._retry_delay(attempt, response)
                    if delay is not None:
                        time.sleep(delay)
                        continue
                if response.status_code == 429:
                    raise AIProviderRateLimitedError(
                        "Gemini rate limited content generation. Please retry later."
                    )
                raise AIProviderUnavailableError(
                    "Gemini is temporarily unavailable while generating content. Retry later."
                )
            if not 200 <= response.status_code < 300:
                request_id = self._request_id(response)
                logger.warning(
                    "Gemini generation request rejected: status=%d model=%s request_id=%s attempt=%d",
                    response.status_code,
                    model,
                    request_id or "unavailable",
                    attempt,
                )
            break

        if response is None:
            raise AIProviderNetworkError(
                "Could not reach Gemini to generate content. Check the connection and retry."
            )
        if response.status_code in (401, 403) or self._is_invalid_api_key(response):
            raise InvalidAPIKeyError("Gemini API key is invalid")
        if response.status_code == 429:
            raise AIProviderRateLimitedError(
                "Gemini rate limited content generation. Please retry later."
            )
        if response.status_code >= 500:
            raise AIProviderUnavailableError(
                "Gemini is temporarily unavailable while generating content. Retry later."
            )
        if not 200 <= response.status_code < 300:
            raise AIProviderInvalidRequestError(
                "Gemini rejected the generation request. Check that the selected model supports content generation and structured JSON output."
            )
        try:
            return response.json()
        except (ValueError, TypeError):
            raise AIProviderInvalidResponseError(
                "Gemini API returned malformed JSON"
            ) from None

    @staticmethod
    def _is_invalid_api_key(response: httpx.Response) -> bool:
        if response.status_code != 400:
            return False
        try:
            payload = response.json()
            error = payload.get("error", {}) if isinstance(payload, dict) else {}
            details = error.get("details", []) if isinstance(error, dict) else []
            message = error.get("message", "") if isinstance(error, dict) else ""
        except (AttributeError, ValueError, TypeError):
            return False
        return bool(
            re.search(r"\bapi key (?:is )?(?:not valid|invalid)\b", message, re.IGNORECASE)
        ) or (isinstance(details, list) and any(
            isinstance(detail, dict) and detail.get("reason") == "API_KEY_INVALID"
            for detail in details
        ))

    @staticmethod
    def _request_id(response: httpx.Response) -> str | None:
        request_id = (
            response.headers.get("x-goog-request-id")
            or response.headers.get("x-request-id")
        )
        if not request_id:
            return None
        return re.sub(r"[^A-Za-z0-9._:-]", "", request_id)[:128] or None

    @classmethod
    def _log_response_failure(cls, response: httpx.Response, *, model: str) -> None:
        logger.warning(
            "Gemini request rejected: status=%d model=%s request_id=%s attempt=1",
            response.status_code,
            model,
            cls._request_id(response) or "unavailable",
        )

    @staticmethod
    def _retry_delay(attempt: int, response: httpx.Response | None = None) -> float | None:
        if response is not None:
            retry_after = response.headers.get("retry-after")
            if retry_after is not None:
                try:
                    delay = float(retry_after)
                except ValueError:
                    try:
                        retry_at = parsedate_to_datetime(retry_after)
                        if retry_at.tzinfo is None:
                            retry_at = retry_at.replace(tzinfo=timezone.utc)
                        delay = (retry_at - datetime.now(timezone.utc)).total_seconds()
                    except (TypeError, ValueError, OverflowError):
                        delay = -1
                if delay >= 0:
                    return delay if delay <= _RETRY_MAX_DELAY_SECONDS else None
        return min(
            _RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)),
            _RETRY_MAX_DELAY_SECONDS,
        ) * random.uniform(0.8, 1.2)
