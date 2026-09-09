from typing import Protocol, Any, Dict, Optional
from fastapi import Request, Response
from app.auth.context import AuthContext

class AuthProvider(Protocol):
    """
    Abstract base defining the authentication provider interface.
    """
    async def resolve_identity(self, request: Request) -> AuthContext | None:
        """Resolve the authenticated identity from the given request."""
        ...
        
    async def login(self, request: Request, response: Response, data: Optional[Dict[str, Any]] = None) -> Any:
        """Process a login request. Extended to support request/response mutation for cookies."""
        ...
        
    async def logout(self, request: Request, response: Response) -> Any:
        """Process a logout request. Extended to support request/response mutation for cookies."""
        ...
