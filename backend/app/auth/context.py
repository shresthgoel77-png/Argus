from pydantic import BaseModel

class AuthContext(BaseModel):
    """
    Represents a resolved authenticated identity.
    This is provider-agnostic.
    """
    external_id: str
    email: str
    provider: str
