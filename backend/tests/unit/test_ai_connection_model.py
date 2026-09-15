import uuid
import pytest
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from app.models.ai_connection import AIConnection
from app.models.user import User

def test_ai_connection_model_unique_user_id(db_session):
    # Create user
    user = User(
        email="testai@example.com",
        auth_provider="github",
        external_auth_id="12345"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Create first connection
    connection1 = AIConnection(
        user_id=user.id,
        provider="gemini",
        model="gemini-1.5-pro",
        encrypted_api_key="encrypted_dummy_key"
    )
    db_session.add(connection1)
    db_session.commit()

    # Create second connection for same user (should fail)
    connection2 = AIConnection(
        user_id=user.id,
        provider="openai",
        model="gpt-4",
        encrypted_api_key="another_encrypted_key"
    )
    db_session.add(connection2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

def test_ai_connection_no_plaintext_keys():
    # Introspect AIConnection model to ensure no plaintext api keys are present
    columns = AIConnection.__table__.columns.keys()
    
    # We should have exactly encrypted_api_key
    assert "encrypted_api_key" in columns
    
    # Disallowed fuzzy patterns that suggest plaintext
    disallowed = ["api_key", "token", "password", "secret", "plaintext"]
    for col in columns:
        if col == "encrypted_api_key":
            continue
        for bad in disallowed:
            assert bad not in col.lower(), f"Found potentially plaintext key column: {col}"

def test_ai_connection_fields(db_session):
    # Verify all expected column defaults and timestamps
    user = User(
        email="testfields@example.com",
        auth_provider="github",
        external_auth_id="123456"
    )
    db_session.add(user)
    db_session.commit()

    connection = AIConnection(
        user_id=user.id,
        provider="gemini",
        model="gemini-1.5-pro",
        encrypted_api_key="enc_key"
    )
    db_session.add(connection)
    db_session.commit()
    db_session.refresh(connection)

    assert connection.status == "valid"
    assert isinstance(connection.last_validated_at, datetime)
    assert connection.last_error is None
    assert connection.last_used_at is None
    assert isinstance(connection.created_at, datetime)
    assert isinstance(connection.updated_at, datetime)
