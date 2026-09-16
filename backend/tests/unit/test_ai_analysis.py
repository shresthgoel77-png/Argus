import pytest
from app.models.ai_analysis import AIAnalysis
from app.models.finding import Finding
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import uuid
from sqlalchemy import inspect

def test_aianalysis_creation(db_session, test_user):
    from app.models.github_connection import GitHubConnection
    from app.models.repository import Repository
    
    conn = GitHubConnection(user_id=test_user.id, installation_id=123, account_login="test_user", account_type="User")
    db_session.add(conn)
    db_session.commit()
    
    repo = Repository(connection_id=conn.id, github_repo_id=456, full_name="user/test")
    db_session.add(repo)
    db_session.commit()
    
    finding = Finding(
        repository_id=repo.id,
        category="security",
        type="vulnerability",
        title="Test Finding",
        description="A test finding.",
        severity="high",
        status="open",
        source="test",
        evidence={}
    )
    db_session.add(finding)
    db_session.commit()
    
    analysis = AIAnalysis(
        finding_id=finding.id,
        analysis_type="finding_explanation",
        status="pending",
        provider="gemini",
        model="gemini-1.5-pro",
        summary="Initial summary",
        severity_assessment="high",
        confidence=0.9,
    )
    db_session.add(analysis)
    db_session.commit()
    
    assert analysis.id is not None
    assert analysis.finding_id == finding.id
    assert analysis.analysis_type == "finding_explanation"
    assert analysis.status == "pending"
    assert analysis.provider == "gemini"
    assert analysis.model == "gemini-1.5-pro"
    assert analysis.requested_at is not None
    assert analysis.completed_at is None
    assert analysis.severity_assessment == "high"

def test_aianalysis_fk_cascade():
    fk = list(AIAnalysis.__table__.c.finding_id.foreign_keys)[0]
    assert fk.ondelete == "CASCADE"

def test_aianalysis_query_ordering(db_session, test_user):
    from app.models.github_connection import GitHubConnection
    from app.models.repository import Repository
    
    conn = GitHubConnection(user_id=test_user.id, installation_id=999, account_login="test_query", account_type="User")
    db_session.add(conn)
    db_session.commit()
    
    repo = Repository(connection_id=conn.id, github_repo_id=1111, full_name="user/query")
    db_session.add(repo)
    db_session.commit()
    
    finding = Finding(
        repository_id=repo.id,
        category="security",
        type="vulnerability",
        title="Test Query",
        description="A test finding.",
        severity="high",
        status="open",
        source="test",
        evidence={}
    )
    db_session.add(finding)
    db_session.commit()
    
    import time
    a1 = AIAnalysis(finding_id=finding.id, provider="gemini", model="gemini-1.5-pro")
    db_session.add(a1)
    db_session.commit()
    
    time.sleep(1.0)
    
    a2 = AIAnalysis(finding_id=finding.id, provider="gemini", model="gemini-1.5-pro")
    db_session.add(a2)
    db_session.commit()
    
    results = db_session.query(AIAnalysis).filter_by(finding_id=finding.id).order_by(AIAnalysis.requested_at.desc()).all()
    assert len(results) == 2
    assert results[0].id == a2.id
    assert results[1].id == a1.id
