import time
import pytest
import uuid
import random
from app.models.user import User
from app.models.github_connection import GitHubConnection
from app.models.repository import Repository
from app.services.finding_service import create_finding, list_findings_for_repository

@pytest.fixture
def repo_for_findings(db_session):
    unique_id = uuid.uuid4().hex[:8]
    user = User(email=f"testf_{unique_id}@example.com", auth_provider="test")
    db_session.add(user)
    db_session.flush()

    conn = GitHubConnection(
        user_id=user.id,
        installation_id=random.randint(10000, 99999),
        account_login=f"test_acc_{unique_id}",
        account_type="User"
    )
    db_session.add(conn)
    db_session.flush()

    repo = Repository(
        connection_id=conn.id,
        github_repo_id=random.randint(10000, 99999),
        full_name=f"test_acc_{unique_id}/repo"
    )
    db_session.add(repo)
    db_session.commit()
    return repo

def test_create_finding(db_session, repo_for_findings):
    finding = create_finding(
        db_session,
        repository_id=repo_for_findings.id,
        category="security",
        type_="secret_leak",
        title="Secret Found",
        description="A secret was found.",
        severity="critical",
        source="scanner",
        evidence={"line": 42}
    )
    assert finding.id is not None
    assert finding.repository_id == repo_for_findings.id
    assert finding.category == "security"
    assert finding.type == "secret_leak"
    assert finding.title == "Secret Found"
    assert finding.description == "A secret was found."
    assert finding.severity == "critical"
    assert finding.source == "scanner"
    assert finding.evidence == {"line": 42}
    assert finding.status == "open"
    assert finding.detected_at is not None

def test_list_findings_for_repository(db_session, repo_for_findings):
    # clear initial state if any
    
    create_finding(
        db_session,
        repository_id=repo_for_findings.id,
        category="security",
        type_="secret_leak",
        title="Secret 1",
        description="desc1",
        severity="critical",
        source="scanner",
        evidence={}
    )
    time.sleep(0.01) # ensure time separation
    
    create_finding(
        db_session,
        repository_id=repo_for_findings.id,
        category="quality",
        type_="lint",
        title="Quality 1",
        description="desc2",
        severity="low",
        source="linter",
        evidence={}
    )
    time.sleep(0.01)
    
    create_finding(
        db_session,
        repository_id=repo_for_findings.id,
        category="security",
        type_="vuln",
        title="Secret 2",
        description="desc3",
        severity="high",
        source="scanner",
        evidence={}
    )

    findings = list_findings_for_repository(db_session, repo_for_findings.id, limit=2)
    assert len(findings) == 2
    # newest first
    assert findings[0].title == "Secret 2"
    assert findings[1].title == "Quality 1"

    sec_findings = list_findings_for_repository(db_session, repo_for_findings.id, category="security", limit=50)
    assert len(sec_findings) == 2
    assert sec_findings[0].title == "Secret 2"
    assert sec_findings[1].title == "Secret 1"
