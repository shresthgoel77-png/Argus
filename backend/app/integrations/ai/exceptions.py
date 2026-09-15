class AIProviderError(Exception):
    """Base exception for all AI Provider related errors."""
    pass

class InvalidAPIKeyError(AIProviderError):
    """Raised when the provided API key is invalid."""
    pass

class AIProviderUnavailableError(AIProviderError):
    """Raised when the AI Provider is unreachable or responds with 5xx."""
    pass

class AIProviderRateLimitedError(AIProviderError):
    """Raised when the AI Provider rate limits the request."""
    pass

class UnknownProviderError(AIProviderError):
    """Raised when an unregistered AI provider key is requested."""
    pass
