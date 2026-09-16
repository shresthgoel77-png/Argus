"""Small raw HTTP client for Gemini validation and content generation."""

from __future__ import annotations

import httpx

from app.integrations.ai.exceptions import (
    AIProviderInvalidResponseError,
    AIProviderRateLimitedError,
    AIProviderUnavailableError,
    InvalidAPIKeyError,
)

_GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"
_DEFAULT_TIMEOUT_SECONDS = 10.0
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


class GeminiClient:
    """Client for the side-effect-free Gemini models-list validation call."""

    def __init__(
        self,
        *,
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
        http_client: httpx.Client | None = None,
        api_key: str | None = None,
    ) -> None:
        self._timeout = timeout
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

    def generate_content(self, *, model: str, system_instructions: str, untrusted_content: str) -> dict:
        """Return Gemini's structured content response without exposing request data in errors."""
        url = _GEMINI_GENERATE_URL.format(model=model)
        payload = {
            "systemInstruction": {"parts": [{"text": system_instructions}]},
            "contents": [{"role": "user", "parts": [{"text": untrusted_content}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": _RESPONSE_SCHEMA,
            },
        }
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
        except (httpx.TimeoutException, httpx.NetworkError):
            raise AIProviderUnavailableError(
                "Gemini API is unavailable while generating analysis"
            ) from None
        except httpx.HTTPError:
            raise AIProviderUnavailableError(
                "Gemini API request failed while generating analysis"
            ) from None

        if response.status_code in (401, 403):
            raise InvalidAPIKeyError("Gemini API key is invalid")
        if response.status_code == 429:
            raise AIProviderRateLimitedError("Gemini API rate limit exceeded")
        if response.status_code >= 500:
            raise AIProviderUnavailableError("Gemini API is unavailable")
        if not 200 <= response.status_code < 300:
            raise AIProviderUnavailableError("Gemini API rejected the analysis request")
        try:
            return response.json()
        except (ValueError, TypeError):
            raise AIProviderInvalidResponseError(
                "Gemini API returned malformed JSON"
            ) from None
