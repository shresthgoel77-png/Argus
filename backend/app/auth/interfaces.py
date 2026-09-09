from typing import Protocol, Any, Dict
from fastapi import Request
from app.auth.context import AuthContext

class AuthProvider(Protocol):
    """
    Abstract base defining the authentication provider interface.
    """
    async def resolve_identity(self, request: Request) -> AuthContext | None:
        """Resolve the authenticated identity from the given request."""
        ...
        
    async def login(self, data: Dict[str, Any]) -> Any:
        """Process a login request."""
        ...
        
    async def logout(self, request: Request) -> Any:
        """Process a logout request."""
        ...
