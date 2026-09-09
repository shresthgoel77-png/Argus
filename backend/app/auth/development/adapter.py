from typing import Any, Dict, Optional
from fastapi import Request, Response
from app.auth.interfaces import AuthProvider
from app.auth.context import AuthContext
from .constants import DEV_USER_EMAIL, DEV_USER_EXTERNAL_ID

class DevelopmentAuthProvider(AuthProvider):
    """
    Concrete deterministic development/test authentication provider.
    Reads and writes a deterministic developer session using Starlette's 
    signed SessionMiddleware in `request.session`.
    """
    
    async def resolve_identity(self, request: Request) -> AuthContext | None:
        """
        Reads the signed session cookie data from request.session.
        If populated with the dev marker, returns the deterministic dev identity.
        Otherwise, returns None.
        """
        if request.session.get("dev_auth_active"):
            return AuthContext(
                email=DEV_USER_EMAIL,
                external_id=DEV_USER_EXTERNAL_ID,
                provider="development"
            )
        return None

    async def login(self, request: Request, response: Response, data: Optional[Dict[str, Any]] = None) -> Any:
        """
        Writes the signed session identifying the deterministic dev user.
        Takes no real credentials since there is exactly one identity.
        """
        request.session["dev_auth_active"] = True
        return {"status": "success", "message": "Development session started"}

    async def logout(self, request: Request, response: Response) -> Any:
        """
        Clears the session cookie identifying the deterministic dev user.
        """
        request.session.clear()
        return {"status": "success", "message": "Development session cleared"}
