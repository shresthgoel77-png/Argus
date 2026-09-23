import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock

from app.monitoring.analyzers.issue_analyzer import IssueAnalyzer
from app.models.user import User
from app.models.github_connection import GitHubConnection
from app.models.repository import Repository
from app.models.finding import Finding
import uuid

@pytest.fixture
def repo_for_scan(db_session):
    unique_id = uuid.uuid4().hex[:8]
    user = User(email=f"scan_{unique_id}@example.com", auth_provider="test")
    db_session.add(user)
    db_session.flush()

    conn = GitHubConnection(
        user_id=user.id,
        installation_id=12345,
        account_login=f"scan_acc_{unique_id}",
        account_type="User"
    )
    db_session.add(conn)
    db_session.flush()

    repo = Repository(
        connection_id=conn.id,
        github_repo_id=12345,
        full_name=f"scan_acc_{unique_id}/repo"
    )
    db_session.add(repo)
    db_session.commit()
    return repo

@pytest.mark.asyncio
async def test_rescanning_stale_issue_does_not_create_duplicate(db_session, repo_for_scan):
    analyzer = IssueAnalyzer()
    client = AsyncMock()
    
    stale_date = datetime.now(timezone.utc) - timedelta(days=35)
    
    client.list_repository_issues.return_value = [
        {"number": 100, "updated_at": stale_date.isoformat(), "html_url": "url_stale"}
    ]
    
    # Run first scan
    await analyzer.scan_repository_for_stale_issues(db_session, repo_for_scan, client)
    
    # Verify one finding is created
    findings_1 = db_session.query(Finding).filter(Finding.repository_id == repo_for_scan.id).all()
    assert len(findings_1) == 1
    assert findings_1[0].fingerprint == "stale_issue_100"
    
    # Run second scan (re-scan)
    await analyzer.scan_repository_for_stale_issues(db_session, repo_for_scan, client)
    
    # Verify no duplicate finding is added
    findings_2 = db_session.query(Finding).filter(Finding.repository_id == repo_for_scan.id).all()
    assert len(findings_2) == 1
    assert findings_2[0].id == findings_1[0].id
