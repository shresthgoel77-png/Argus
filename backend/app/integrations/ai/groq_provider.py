"""Groq implementation of the application AI provider contract."""

from __future__ import annotations

from dataclasses import replace
from pydantic import ValidationError

from app.bot.context_builder import BotContext
from app.core.config import settings
from app.integrations.ai.exceptions import AIProviderInvalidResponseError
from app.integrations.ai.groq_client import GroqClient
from app.integrations.ai.provider_base import BaseAIProvider, BotResponseResult, StructuredAnalysisResult
from app.schemas.repository_summary_result import RepositorySummaryResult
from app.services.ai_context_common import bounded_generation_content
from app.services.ai_context_builder import FindingContext
from app.services.repository_summary_context_builder import RepositorySummaryContext


class GroqProvider(BaseAIProvider):
    key = "groq"
    SUPPORTED_MODELS = [
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
        "qwen/qwen3.8-27b",
    ]
    DEFAULT_MODEL = "openai/gpt-oss-20b"

    def __init__(self, client: GroqClient | None = None, *, api_key: str | None = None,
                 model: str | None = None) -> None:
        self._client = client or GroqClient(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    def validate_api_key(self, api_key: str) -> None:
        self._client.validate_api_key(api_key)

    def validate_model(self, api_key: str, model: str) -> None:
        self._client.validate_model(api_key, model)

    def _generate(self, context, schema: dict, name: str):
        try:
            response = self._client.generate(
                model=self._model,
                system_instructions=context.system_instructions,
                content=bounded_generation_content(context.untrusted_content),
                schema=schema,
                max_tokens=settings.ai_max_output_tokens,
            )
            generated_text = response["choices"][0]["message"]["content"]
            return generated_text
        except (KeyError, IndexError, TypeError, AttributeError):
            raise AIProviderInvalidResponseError(f"Groq returned an invalid {name} response.") from None

    def generate_analysis(self, context: FindingContext) -> StructuredAnalysisResult:
        try:
            return StructuredAnalysisResult.model_validate_json(self._generate(
                context, StructuredAnalysisResult.model_json_schema(), "analysis"))
        except (TypeError, ValidationError, ValueError):
            raise AIProviderInvalidResponseError("Groq returned an invalid analysis response.") from None

    def generate_repository_summary(self, context: RepositorySummaryContext) -> RepositorySummaryResult:
        try:
            return RepositorySummaryResult.model_validate_json(self._generate(
                context, RepositorySummaryResult.model_json_schema(), "repository summary"))
        except (TypeError, ValidationError, ValueError):
            raise AIProviderInvalidResponseError("Groq returned an invalid repository summary response.") from None

    def generate_bot_response(self, context: BotContext) -> BotResponseResult:
        instructions = (
            f"{context.system_instructions}\nThis is a GitHub comment. Keep it concise and use plain text or Markdown. "
            "Explain only; never imply that you modified code."
        )
        bot_context = replace(context, system_instructions=instructions)
        try:
            return BotResponseResult.model_validate_json(self._generate(
                bot_context, BotResponseResult.model_json_schema(), "bot"))
        except (TypeError, ValidationError, ValueError):
            raise AIProviderInvalidResponseError("Groq returned an invalid bot response.") from None
