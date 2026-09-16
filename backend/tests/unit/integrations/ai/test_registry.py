import pytest
from app.integrations.ai import register_provider, get_provider
from app.integrations.ai.provider_base import BaseAIProvider
from app.integrations.ai.exceptions import (
    UnknownProviderError, AIProviderError, InvalidAPIKeyError
)

class DummyProvider(BaseAIProvider):
    key = "dummy"
    SUPPORTED_MODELS = ["dummy-model"]
    DEFAULT_MODEL = "dummy-model"

    def validate_api_key(self, api_key: str) -> None:
        if api_key != "valid_key":
            raise InvalidAPIKeyError("Invalid key")

    def generate_analysis(self, context):
        raise NotImplementedError

def test_ai_provider_registry():
    # Register the provider
    register_provider("dummy", DummyProvider)
    
    # Retrieve the provider class by key
    provider_class = get_provider("dummy")
    assert provider_class is DummyProvider
    
    # Verify instantiation and method
    provider_instance = provider_class()
    assert provider_instance.key == "dummy"
    assert provider_instance.DEFAULT_MODEL == "dummy-model"
    
    # Unknown key raises exception
    with pytest.raises(UnknownProviderError):
        get_provider("non_existent_provider")

def test_ai_provider_exceptions():
    provider = DummyProvider()
    
    # Should not raise exception
    provider.validate_api_key("valid_key")
    
    # Should raise specific exception subclasses
    with pytest.raises(InvalidAPIKeyError):
        provider.validate_api_key("invalid_key")
    
    # Test hierarchy
    assert issubclass(InvalidAPIKeyError, AIProviderError)
    assert issubclass(UnknownProviderError, AIProviderError)
