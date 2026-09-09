from sqlalchemy.orm import Session
from app.models.user import User
from app.auth.context import AuthContext

def get_or_create_user_from_context(db: Session, auth_context: AuthContext) -> User:
    """
    Looks up a User by external_auth_id + auth_provider.
    If not found, creates the user deterministically from the AuthContext.
    """
    user = db.query(User).filter(
        User.external_auth_id == auth_context.external_id,
        User.auth_provider == auth_context.provider
    ).first()

    if user:
        return user

    # Create new user if not found
    user = User(
        email=auth_context.email,
        auth_provider=auth_context.provider,
        external_auth_id=auth_context.external_id,
        display_name=None
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
