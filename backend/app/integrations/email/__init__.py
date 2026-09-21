from typing import Type

from .provider_base import BaseEmailProvider, EmailSendResult
from .smtp_provider import SMTPEmailProvider


class UnknownEmailProviderError(Exception):
    """Raised when an unrecognized email provider key is requested."""
    pass


EMAIL_PROVIDER_REGISTRY: dict[str, Type[BaseEmailProvider]] = {}

def register_provider(key: str, provider_class: Type[BaseEmailProvider]) -> None:
    EMAIL_PROVIDER_REGISTRY[key] = provider_class

def get_provider(key: str) -> Type[BaseEmailProvider]:
    provider = EMAIL_PROVIDER_REGISTRY.get(key)
    if provider is None:
        raise UnknownEmailProviderError(f"Email provider '{key}' is not recognized.")
    return provider


# Register default providers
register_provider(SMTPEmailProvider.key, SMTPEmailProvider)
