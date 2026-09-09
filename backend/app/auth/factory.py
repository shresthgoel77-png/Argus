from app.core.config import settings
from app.auth.interfaces import AuthProvider

def get_auth_provider() -> AuthProvider:
    """
    Validates settings based on environment, returning the concrete AuthProvider.
    """
    if settings.app_env == "production":
        # Note: redundant safety check over Config model check
        if settings.auth_provider == "development":
            raise ValueError("DevelopmentAuthProvider must never be instantiated in production.")
            
    if settings.auth_provider == "development":
        # Lazy import avoids circular dependencies or unnecessary load in production later
        from app.auth.development.adapter import DevelopmentAuthProvider
        return DevelopmentAuthProvider()
        
    raise NotImplementedError(f"AuthProvider {settings.auth_provider} is not implemented.")
