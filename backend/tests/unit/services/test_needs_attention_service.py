import uuid

import pytest

from app.models.finding import Finding
from app.models.repository_health_snapshot import RepositoryHealthSnapshot
from app.services.needs_attention_service import get_needs_attention


def add_finding(db_session, repository, category, evidence, severity="high", priority=None):
    finding = Finding(
        id=uuid.uuid4(),
        repository_id=repository.id,
        category=category,
        type="test",
        title="Test finding",
        description="Finding description",
        severity=severity,
        status="open",
        source="test",
        evidence=evidence,
        priority=priority,
    )
    db_session.add(finding)
    db_session.commit()
    return finding


def add_snapshot(db_session, repository, reasons):
    snapshot = RepositoryHealthSnapshot(
        repository_id=repository.id,
        overall_score=50,
        category_scores={},
        reasons=reasons,
    )
    db_session.add(snapshot)
    db_session.commit()
    return snapshot


def test_get_needs_attention_empty_repository(db_session, test_user_repository):
    result = get_needs_attention(db_session, test_user_repository.id)
    assert result.findings == []
    assert result.health_snapshot is None
    assert result.reasons == []


def test_get_needs_attention_low_severity_only(db_session, test_user_repository):
    add_finding(db_session, test_user_repository, "security", {}, severity="low")
    add_finding(db_session, test_user_repository, "security", {}, severity="medium")
    result = get_needs_attention(db_session, test_user_repository.id)
    
    assert result.findings == []
    assert result.health_snapshot is None


def test_get_needs_attention_no_snapshot(db_session, test_user_repository):
    add_finding(db_session, test_user_repository, "security", {}, severity="critical", priority="P0")
    result = get_needs_attention(db_session, test_user_repository.id)
    
    assert len(result.findings) == 1
    assert result.findings[0].severity == "critical"
    assert result.health_snapshot is None
    assert result.reasons == []


def test_get_needs_attention_with_snapshot_and_limit(db_session, test_user_repository):
    add_finding(db_session, test_user_repository, "security", {}, severity="high")
    add_finding(db_session, test_user_repository, "security", {}, severity="critical")
    add_finding(db_session, test_user_repository, "security", {}, severity="high")
    add_snapshot(db_session, test_user_repository, ["Bad things"])
    
    result = get_needs_attention(db_session, test_user_repository.id, limit=2)
    assert len(result.findings) == 2
    assert result.findings[0].severity == "critical"
    assert result.findings[1].severity == "high"
    assert result.health_snapshot is not None
    assert result.reasons == ["Bad things"]
