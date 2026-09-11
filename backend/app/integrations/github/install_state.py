import time
import uuid
from typing import TypedDict
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from app.core.config import settings

class InstallStatePayload(TypedDict):
    user_id: str
    issued_at: float

def get_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        secret_key=settings.session_secret_key,
        salt="github-install-state"
    )

def generate_install_state(user_id: uuid.UUID) -> str:
    """Generates a signed state token for the GitHub App installation flow."""
    serializer = get_serializer()
    payload: InstallStatePayload = {
        "user_id": str(user_id),
        "issued_at": time.time()
    }
    return serializer.dumps(payload)

def verify_install_state(state: str) -> InstallStatePayload:
    """
    Verifies the state token and returns the payload. 
    Raises ValueError on failure (expired or invalid signature).
    """
    serializer = get_serializer()
    try:
        payload = serializer.loads(
            state,
            max_age=settings.github_app_install_state_ttl_seconds
        )
        return payload
    except SignatureExpired:
        raise ValueError("Installation state has expired")
    except BadSignature:
        raise ValueError("Invalid installation state signature")
