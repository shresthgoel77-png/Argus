from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from app.bot.context_builder import BotContext
from app.services.ai_context_builder import FindingContext


class StructuredAnalysisResult(BaseModel):
    summary: str
    severity: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning_summary: str | None = None
    recommendations: list[str]

class BotResponseResult(BaseModel):
    answer_text: str
    key_points: list[str] | None = None
    confidence: float = Field(ge=0.0, le=1.0)

class BaseAIProvider(ABC):
    key: str
    SUPPORTED_MODELS: list[str]
    DEFAULT_MODEL: str

    @abstractmethod
    def validate_api_key(self, api_key: str) -> None:
        """
        Validates the given API key.
        Should raise a structured exception (e.g. InvalidAPIKeyError, 
        AIProviderUnavailableError) on failure instead of silently returning booleans.
        """
        pass

    @abstractmethod
    def generate_analysis(self, context: FindingContext) -> StructuredAnalysisResult:
        """Generate a structured explanation for a finding context."""
        pass

    @abstractmethod
    def generate_bot_response(self, context: BotContext) -> BotResponseResult:
        """Generate a conversational bot response for a GitHub context."""
        pass
