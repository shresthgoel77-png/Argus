import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.encryption import decrypt_secret, encrypt_secret
from app.integrations.ai import get_provider
from app.models.ai_connection import AIConnection


def create_or_replace_connection(
    db: Session,
    user_id: uuid.UUID,
    provider_key: str,
    model: str,
    api_key: str,
) -> AIConnection:
    """Validate, encrypt, and persist the user's single AI connection."""
    provider_class = get_provider(provider_key)
    if model not in provider_class.SUPPORTED_MODELS:
        raise ValueError(
            f"Model '{model}' is not supported by AI provider '{provider_key}'."
        )

    provider_class().validate_api_key(api_key)
    encrypted_api_key = encrypt_secret(api_key)
    validated_at = datetime.now(timezone.utc)

    connection = db.query(AIConnection).filter(
        AIConnection.user_id == user_id
    ).first()
    if connection is None:
        connection = AIConnection(user_id=user_id)
        db.add(connection)

    connection.provider = provider_key
    connection.model = model
    connection.encrypted_api_key = encrypted_api_key
    connection.status = "valid"
    connection.last_validated_at = validated_at
    connection.last_error = None

    db.commit()
    db.refresh(connection)
    return connection


def get_connection_status(
    db: Session, user_id: uuid.UUID
) -> dict[str, object] | None:
    """Return the configured connection's safe, non-secret status fields."""
    connection = db.query(AIConnection).filter(
        AIConnection.user_id == user_id
    ).first()
    if connection is None:
        return None

    return {
        "provider": connection.provider,
        "model": connection.model,
        "status": connection.status,
        "last_validated_at": connection.last_validated_at,
    }


def delete_connection(db: Session, user_id: uuid.UUID) -> None:
    """Delete the user's AI connection, if one is configured."""
    connection = db.query(AIConnection).filter(
        AIConnection.user_id == user_id
    ).first()
    if connection is None:
        return

    db.delete(connection)
    db.commit()


def get_decrypted_api_key(db: Session, user_id: uuid.UUID) -> str:
    """Return the plaintext key for internal service-to-service use only.

    This function must never be called from an API route handler. It exists
    solely for future internal AI-calling services in Phase 10.
    """
    connection = db.query(AIConnection).filter(
        AIConnection.user_id == user_id
    ).first()
    if connection is None:
        raise ValueError("No AI connection is configured for this user.")

    return decrypt_secret(connection.encrypted_api_key)