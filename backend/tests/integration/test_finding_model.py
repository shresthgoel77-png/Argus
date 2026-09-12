import pytest
from sqlalchemy.exc import IntegrityError
from app.models.finding import Finding
from app.models.repository import Repository
from app.models.github_connection import GitHubConnection
from app.models.user import User

def test_finding_insert(db_session):
    import uuid
    import random
    
    unique_id = uuid.uuid4().hex[:8]
    user = User(email=f"testf_{unique_id}@example.com", auth_provider="test")
    db_session.add(user)
    db_session.flush()

    conn = GitHubConnection(
        user_id=user.id,
        installation_id=random.randint(100000, 99999999),
        account_login=f"test_acc_{unique_id}",
        account_type="User"
    )
    db_session.add(conn)
    db_session.flush()

    repo = Repository(
        connection_id=conn.id,
        github_repo_id=random.randint(100000, 99999999),
        full_name=f"test_acc_{unique_id}/repo"
    )
    db_session.add(repo)
    db_session.flush()

    finding = Finding(
        repository_id=repo.id,
        category="security",
        type="secret_leak",
        title="Secret Found",
        description="A secret was found.",
        severity="critical",
        source="scanner",
        evidence={"foo": "bar"}
    )
    db_session.add(finding)
    db_session.commit()

    saved = db_session.query(Finding).filter_by(title="Secret Found").first()
    assert saved is not None
    assert saved.repository_id == repo.id
    assert saved.category == "security"
    assert saved.status == "open"
    assert saved.evidence == {"foo": "bar"}
    assert saved.detected_at is not None
    assert saved.updated_at is not None


