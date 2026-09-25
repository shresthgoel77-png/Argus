from typing import Any, Dict, Optional

from clerk_backend_api import Clerk
from clerk_backend_api.security.types import AuthenticateRequestOptions
from fastapi import Request

from app.auth.context import AuthContext
from app.auth.interfaces import AuthProvider


class ClerkAuthAdapter(AuthProvider):
    """Resolve identities from verified Clerk session tokens.

    The SDK performs signature, expiry, and claim validation. Supplying a JWT
    key keeps verification local; supplying a Clerk secret key lets the SDK
    retrieve Clerk's public keys when a local key is not configured.
    """

    def __init__(
        self,
        *,
        secret_key: str | None = None,
        jwt_key: str | None = None,
        authorized_parties: list[str] | None = None,
        clerk_client: Any | None = None,
    ) -> None:
        if not secret_key and not jwt_key and clerk_client is None:
            raise ValueError("Clerk verification requires a secret key or JWT key")

        self._jwt_key = jwt_key
        self._authorized_parties = authorized_parties
        self._clerk = clerk_client or Clerk(bearer_auth=secret_key)

    async def resolve_identity(self, request: Request) -> AuthContext | None:
        """Return the verified Clerk identity, or ``None`` on auth failure."""
        try:
            state = self._clerk.authenticate_request(
                request,
                AuthenticateRequestOptions(
                    jwt_key=self._jwt_key,
                    authorized_parties=self._authorized_parties,
                ),
            )
        except Exception:
            return None

        if not state.is_signed_in or not state.payload:
            return None

        external_id = state.payload.get("sub")
        email = state.payload.get("email")
        if not isinstance(external_id, str) or not external_id:
            return None
        if not isinstance(email, str) or not email:
            return None

        return AuthContext(
            external_id=external_id,
            email=email,
            provider="clerk",
        )

    async def login(
        self, request: Request, data: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Clerk sessions are established by Clerk's frontend SDK."""
        return None

    async def logout(self, request: Request) -> Any:
        """Clerk sessions are ended by Clerk's frontend SDK."""
        return None