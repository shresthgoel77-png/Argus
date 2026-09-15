from typing import Type
from .provider_base import BaseAIProvider
from .exceptions import UnknownProviderError
from .gemini_provider import GeminiProvider

AI_PROVIDER_REGISTRY: dict[str, Type[BaseAIProvider]] = {}

def register_provider(key: str, provider_class: Type[BaseAIProvider]) -> None:
    AI_PROVIDER_REGISTRY[key] = provider_class

def get_provider(key: str) -> Type[BaseAIProvider]:
    provider = AI_PROVIDER_REGISTRY.get(key)
    if provider is None:
        raise UnknownProviderError(f"AI provider '{key}' is not recognized.")
    return provider


# Built-in providers are registered on package import, matching the existing
# analyzer registration convention used by the application.
register_provider(GeminiProvider.key, GeminiProvider)
