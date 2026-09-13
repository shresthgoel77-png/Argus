import pytest
from sqlalchemy.exc import IntegrityError
from app.models.finding import Finding
from app.models.repository import Repository
from sqlalchemy.orm import Session

def test_partial_unique_index_on_finding(db_session: Session, test_repository: Repository):
    # Create two findings with the same fingerprint but open status
    f1 = Finding(
        repository_id=test_repository.id,
        category="security",
        type="secret_leak",
        title="Test 1",
        description="Desc 1",
        severity="high",
        status="open",
        source="analyzer_1",
        evidence={},
        fingerprint="fingerprint_123"
    )
    db_session.add(f1)
    db_session.commit()

    f2 = Finding(
        repository_id=test_repository.id,
        category="security",
        type="secret_leak",
        title="Test 2",
        description="Desc 2",
        severity="high",
        status="open",
        source="analyzer_1",
        evidence={},
        fingerprint="fingerprint_123"
    )
    db_session.add(f2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

def test_partial_unique_index_allows_multiple_resolved(db_session: Session, test_repository: Repository):
    # Two resolved findings with the same fingerprint can coexist
    f1 = Finding(
        repository_id=test_repository.id,
        category="security",
        type="secret_leak",
        title="Test 1",
        description="Desc 1",
        severity="high",
        status="resolved",
        source="analyzer_1",
        evidence={},
        fingerprint="fingerprint_abc"
    )
    db_session.add(f1)
    db_session.commit()

    f2 = Finding(
        repository_id=test_repository.id,
        category="security",
        type="secret_leak",
        title="Test 2",
        description="Desc 2",
        severity="high",
        status="resolved",
        source="analyzer_1",
        evidence={},
        fingerprint="fingerprint_abc"
    )
    db_session.add(f2)
    db_session.commit()  # Should not raise

def test_partial_unique_index_ignores_null_fingerprint(db_session: Session, test_repository: Repository):
    # Multiple open findings with NULL fingerprint can coexist
    f1 = Finding(
        repository_id=test_repository.id,
        category="security",
        type="secret_leak",
        title="Test 1",
        description="Desc 1",
        severity="high",
        status="open",
        source="analyzer_1",
        evidence={},
        fingerprint=None
    )
    db_session.add(f1)
    db_session.commit()

    f2 = Finding(
        repository_id=test_repository.id,
        category="security",
        type="secret_leak",
        title="Test 2",
        description="Desc 2",
        severity="high",
        status="open",
        source="analyzer_1",
        evidence={},
        fingerprint=None
    )
    db_session.add(f2)
    db_session.commit()  # Should not raise
