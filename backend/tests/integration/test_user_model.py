import uuid
import pytest
from sqlalchemy.exc import IntegrityError
from app.models.user import User

def test_create_user(db_session):
    user = User(
        email="test@example.com",
        display_name="Test User",
        auth_provider="development",
        external_auth_id="dev_123"
    )
    db_session.add(user)
    db_session.commit()
    
    assert user.id is not None
    assert isinstance(user.id, uuid.UUID)
    assert user.email == "test@example.com"
    assert user.display_name == "Test User"
    assert user.auth_provider == "development"
    assert user.external_auth_id == "dev_123"
    assert user.is_active is True
    assert user.created_at is not None
    assert user.updated_at is not None

def test_email_uniqueness(db_session):
    user1 = User(email="unique@example.com", auth_provider="development")
    db_session.add(user1)
    db_session.commit()
    
    user2 = User(email="unique@example.com", auth_provider="other")
    db_session.add(user2)
    
    with pytest.raises(IntegrityError):
        db_session.commit()
