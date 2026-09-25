import uuid

from app.auth.context import AuthContext
from app.models.user import User
from app.services import clerk_identity_service


def clerk_context(suffix: str) -> AuthContext:
    return AuthContext(
        external_id=f"user_clerk_{suffix}",
        email=f"clerk_{suffix}@example.com",
        provider="clerk",
    )


def test_first_clerk_identity_creates_user(db_session):
    context = clerk_context(uuid.uuid4().hex)

    user = clerk_identity_service.get_or_create_clerk_user(db_session, context)

    assert user.email == context.email
    assert user.external_auth_id == context.external_id
    assert user.auth_provider == "clerk"
    assert user.display_name is None


def test_repeat_clerk_identity_returns_existing_user(db_session):
    context = clerk_context(uuid.uuid4().hex)

    first = clerk_identity_service.get_or_create_clerk_user(db_session, context)
    second = clerk_identity_service.get_or_create_clerk_user(db_session, context)

    assert second.id == first.id
    assert db_session.query(User).filter(
        User.external_auth_id == context.external_id
    ).count() == 1


def test_race_on_first_clerk_identity_uses_unique_constraint(
    db_session, SessionLocal, monkeypatch
):
    context = clerk_context(uuid.uuid4().hex)
    competing_session = SessionLocal()
    inserted = False
    original_find = clerk_identity_service._find_user_by_identity

    def find_with_competing_insert(db, auth_context):
        nonlocal inserted
        if not inserted:
            competing_session.add(User(
                email=f"race_{uuid.uuid4().hex}@example.com",
                auth_provider=auth_context.provider,
                external_auth_id=auth_context.external_id,
            ))
            competing_session.commit()
            inserted = True
            return None
        return original_find(db, auth_context)

    monkeypatch.setattr(
        clerk_identity_service, "_find_user_by_identity", find_with_competing_insert
    )
    try:
        resolved = clerk_identity_service.get_or_create_clerk_user(db_session, context)
    finally:
        competing_session.close()

    assert resolved.external_auth_id == context.external_id
    assert db_session.query(User).filter(
        User.external_auth_id == context.external_id
    ).count() == 1