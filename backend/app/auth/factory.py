from functools import lru_cache
from threading import Lock

from app.core.config import settings
from app.auth.interfaces import AuthProvider


_clerk_provider_lock = Lock()


@lru_cache(maxsize=1)
def _get_clerk_provider(
    secret_key: str | None,
    jwt_key: str | None,
    authorized_parties: tuple[str, ...] | None,
) -> AuthProvider:
    # Reuse SDK HTTP pools only. Identities and tokens are verified per request.
    from app.auth.clerk.adapter import ClerkAuthAdapter
    return ClerkAuthAdapter(
        secret_key=secret_key,
        jwt_key=jwt_key,
        authorized_parties=(
            list(authorized_parties) if authorized_parties is not None else None
        ),
    )


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
        # Serialize cold construction; concurrent requests share one SDK client.
        with _clerk_provider_lock:
            return _get_clerk_provider(
                settings.clerk_secret_key.get_secret_value()
                if settings.clerk_secret_key else None,
                settings.clerk_jwt_key,
                tuple(settings.clerk_authorized_parties)
                if settings.clerk_authorized_parties is not None else None,
            )

    raise NotImplementedError(
        f"AuthProvider {settings.auth_provider!r} is not implemented."
    )
