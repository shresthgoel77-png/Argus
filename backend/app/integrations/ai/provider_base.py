from abc import ABC, abstractmethod

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
