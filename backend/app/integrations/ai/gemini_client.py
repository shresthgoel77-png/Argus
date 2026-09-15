"""Small raw HTTP client for validating Gemini API keys."""

from __future__ import annotations

import httpx

from app.integrations.ai.exceptions import (
    AIProviderRateLimitedError,
    AIProviderUnavailableError,
    InvalidAPIKeyError,
)

_GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"
_DEFAULT_TIMEOUT_SECONDS = 10.0


class GeminiClient:
    """Client for the side-effect-free Gemini models-list validation call."""

    def __init__(
        self,
        *,
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._timeout = timeout
        self._http_client = http_client

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
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise AIProviderUnavailableError(
                "Gemini API is unavailable while validating the API key"
            ) from None
        except httpx.HTTPError as exc:
            raise AIProviderUnavailableError(
                "Gemini API request failed while validating the API key"
            ) from None

        if 200 <= response.status_code < 300:
            return
        if response.status_code in (401, 403):
            raise InvalidAPIKeyError("Gemini API key is invalid")
        if response.status_code == 429:
            raise AIProviderRateLimitedError("Gemini API rate limit exceeded")
        if response.status_code >= 500:
            raise AIProviderUnavailableError("Gemini API is unavailable")
        raise AIProviderUnavailableError(
            "Gemini API rejected the API-key validation request"
        )
