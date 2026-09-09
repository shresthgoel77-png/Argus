from typing import Protocol, Any, Dict, Optional
from fastapi import Request
from app.auth.context import AuthContext

class AuthProvider(Protocol):
    """
    Abstract base defining the authentication provider interface.
    """
    async def resolve_identity(self, request: Request) -> AuthContext | None:
        """Resolve the authenticated identity from the given request."""
        ...
        
    async def login(self, request: Request, data: Optional[Dict[str, Any]] = None) -> Any:
        """Process a login request. Added 'request' to allow session manipulation."""
        ...
        
    async def logout(self, request: Request) -> Any:
        """Process a logout request."""
        ...
