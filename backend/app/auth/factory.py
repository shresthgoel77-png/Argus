from app.core.config import settings
from app.auth.interfaces import AuthProvider


def get_auth_provider() -> AuthProvider:
    """
    Environment-gated auth provider selection.

    Clerk is the only application provider. The development adapter is
    available solely to the isolated backend test harness.
    """
    if settings.auth_provider == "development":
        if settings.app_env != "test":
            raise ValueError(
                "DevelopmentAuthProvider must never be instantiated "
                "outside the test environment."
            )
        from app.auth.development.adapter import DevelopmentAuthProvider
        return DevelopmentAuthProvider()

    if settings.auth_provider == "clerk":
        from app.auth.clerk.adapter import ClerkAuthAdapter
        return ClerkAuthAdapter(
            secret_key=(
                settings.clerk_secret_key.get_secret_value()
                if settings.clerk_secret_key else None
            ),
            jwt_key=settings.clerk_jwt_key,
            authorized_parties=settings.clerk_authorized_parties,
        )

    raise NotImplementedError(
        f"AuthProvider {settings.auth_provider!r} is not implemented."
    )
