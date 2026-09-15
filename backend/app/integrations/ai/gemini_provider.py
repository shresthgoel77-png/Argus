"""Gemini implementation of the application AI provider contract."""

from __future__ import annotations

from app.integrations.ai.gemini_client import GeminiClient
from app.integrations.ai.provider_base import BaseAIProvider


class GeminiProvider(BaseAIProvider):
    key = "gemini"

    # Current identifiers from Google's Gemini API models guide (September
    # 2026). These are the text-capable models intended for later generation.
    SUPPORTED_MODELS = [
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-3.1-pro-preview",
        "gemini-3-flash-preview",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    ]
    DEFAULT_MODEL = "gemini-3.8-flash"

    def __init__(self, client: GeminiClient | None = None) -> None:
        self._client = client or GeminiClient()

    def validate_api_key(self, api_key: str) -> None:
        self._client.validate_api_key(api_key)
