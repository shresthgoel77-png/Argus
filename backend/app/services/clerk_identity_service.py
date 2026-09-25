from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.context import AuthContext
from app.models.user import User


def _find_user_by_identity(db: Session, identity: AuthContext) -> User | None:
    return db.query(User).filter(
        User.external_auth_id == identity.external_id,
        User.auth_provider == identity.provider,
    ).first()


def get_or_create_clerk_user(db: Session, identity: AuthContext) -> User:
    """Resolve a User from an already-verified Clerk AuthContext.

    This function must only receive identity data produced by a trusted,
    signature-verifying auth adapter. Raw client-supplied IDs must never be
    passed here. The database uniqueness constraint handles concurrent first
    mappings for the same external identity.
    """
    user = _find_user_by_identity(db, identity)
    if user:
        return user

    user = User(
        email=identity.email,
        auth_provider=identity.provider,
        external_auth_id=identity.external_id,
        display_name=None,
    )

    try:
        with db.begin_nested():
            db.add(user)
            db.flush()
    except IntegrityError:
        user = _find_user_by_identity(db, identity)
        if user:
            return user
        raise

    db.commit()
    db.refresh(user)
    return user