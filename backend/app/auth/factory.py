from app.core.config import settings
from app.auth.interfaces import AuthProvider


def get_auth_provider() -> AuthProvider:
    """
    Environment-gated auth provider selection.

    Development adapter uses a narrow ALLOW-LIST (only "development"
    and "test" environments) — any other environment, including
    production or unrecognised values, is structurally blocked.
    """
    if settings.auth_provider == "development":
        # Narrow allow-list: NOT a deny-list on "production"
        if settings.app_env not in ("development", "test"):
            raise ValueError(
                "DevelopmentAuthProvider must never be instantiated "
                "in production."
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
