import time
import pytest
import uuid
import random
from unittest.mock import patch
from app.models.user import User
from app.models.github_connection import GitHubConnection
from app.models.repository import Repository
from app.monitoring.analyzer_base import FindingDraft
from app.services.finding_lifecycle_service import ignore_finding
from app.services.finding_service import (
    create_finding,
    list_findings_for_repository,
    sync_findings_for_run,
)

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
    assert finding.priority == "critical"


def test_create_finding_fingerprint_conflict_updates_existing_row(db_session, repo_for_findings):
    first = create_finding(
        db_session,
        repository_id=repo_for_findings.id,
        category="security",
        type_="dependency",
        title="Original",
        description="Original description",
        severity="high",
        source="scanner",
        evidence={"count": 1},
        fingerprint="same-fingerprint",
    )
    second = create_finding(
        db_session,
        repository_id=repo_for_findings.id,
        category="security",
        type_="dependency",
        title="Updated",
        description="Updated description",
        severity="high",
        source="scanner",
        evidence={"count": 2},
        fingerprint="same-fingerprint",
    )

    assert second.id == first.id
    assert second.title == "Updated"
    assert second.description == "Updated description"
    assert second.evidence == {"count": 2}
    assert db_session.query(type(first)).count() == 1


def _draft(fingerprint: str, title: str = "Finding") -> FindingDraft:
    return FindingDraft(
        category="security",
        type_="dependency",
        title=title,
        description=f"Description for {title}",
        severity="high",
        evidence={"title": title},
        fingerprint=fingerprint,
    )


def test_sync_findings_for_run_auto_resolves_missing(db_session, repo_for_findings):
    missing = create_finding(
        db_session,
        repository_id=repo_for_findings.id,
        category="security",
        type_="dependency",
        title="Missing",
        description="Missing",
        severity="high",
        source="scanner",
        evidence={},
        fingerprint="missing",
    )

    result = sync_findings_for_run(
        db_session,
        repository_id=repo_for_findings.id,
        category="security",
        analyzer_key="security",
        drafts=[],
    )

    assert missing.status == "resolved"
    assert missing.resolution_source == "auto"
    assert result.auto_resolved == 1


def test_sync_findings_for_run_leaves_ignored_missing_finding_untouched(
    db_session, repo_for_findings
):
    ignored = create_finding(
        db_session,
        repository_id=repo_for_findings.id,
        category="security",
        type_="dependency",
        title="Ignored",
        description="Ignored",
        severity="high",
        source="scanner",
        evidence={},
        fingerprint="ignored",
    )
    ignore_finding(db_session, ignored)

    result = sync_findings_for_run(
        db_session,
        repository_id=repo_for_findings.id,
        category="security",
        analyzer_key="security",
        drafts=[],
    )

    assert ignored.status == "ignored"
    assert result.auto_resolved == 0
    assert result.skipped_ignored == 1


def test_sync_findings_for_run_updates_present_finding(db_session, repo_for_findings):
    existing = create_finding(
        db_session,
        repository_id=repo_for_findings.id,
        category="security",
        type_="dependency",
        title="Before",
        description="Before",
        severity="high",
        source="scanner",
        evidence={"count": 1},
        fingerprint="present",
    )

    result = sync_findings_for_run(
        db_session,
        repository_id=repo_for_findings.id,
        category="security",
        analyzer_key="security",
        drafts=[_draft("present", "After")],
    )

    assert result.created == 0
    assert result.updated == 1
    assert result.auto_resolved == 0
    assert existing.id == db_session.query(type(existing)).one().id
    assert existing.title == "After"
    assert existing.status == "open"

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
    assert findings[0].title == "Secret 2" or findings[0].title == "Secret 1"
    assert findings[1].title == "Quality 1" or findings[1].title == "Secret 1"
    assert findings[1].title == "Quality 1"

    sec_findings = list_findings_for_repository(db_session, repo_for_findings.id, category="security", limit=50)
    assert len(sec_findings) == 2
    titles = [f.title for f in sec_findings]
    assert sorted(titles) == ["Secret 1", "Secret 2"]


@patch("app.services.notification_dispatch_service.dispatch_notification")
def test_create_finding_triggers_dispatch_on_new_critical(mock_dispatch, db_session, repo_for_findings):
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
    assert mock_dispatch.call_count == 1
    mock_dispatch.assert_called_with(
        db_session,
        user_id=repo_for_findings.connection.user_id,
        repository_id=repo_for_findings.id,
        notification_type="finding_created",
        severity="critical",
        title="Secret Found",
        message="A secret was found.",
        reference_type="finding",
        reference_id=str(finding.id)
    )


@patch("app.services.notification_dispatch_service.dispatch_notification")
def test_create_finding_does_not_trigger_on_deduplication(mock_dispatch, db_session, repo_for_findings):
    first = create_finding(
        db_session,
        repository_id=repo_for_findings.id,
        category="security",
        type_="dependency",
        title="Original",
        description="Original desc",
        severity="high",
        source="scanner",
        evidence={},
        fingerprint="dup-test-fingerprint"
    )
    assert mock_dispatch.call_count == 1

    mock_dispatch.reset_mock()

    second = create_finding(
        db_session,
        repository_id=repo_for_findings.id,
        category="security",
        type_="dependency",
        title="Updated",
        description="Updated desc",
        severity="high",
        source="scanner",
        evidence={},
        fingerprint="dup-test-fingerprint"
    )
    assert mock_dispatch.call_count == 0


@patch("app.services.notification_dispatch_service.dispatch_notification")
def test_create_finding_does_not_trigger_on_low_severity(mock_dispatch, db_session, repo_for_findings):
    create_finding(
        db_session,
        repository_id=repo_for_findings.id,
        category="security",
        type_="dependency",
        title="Low Severity",
        description="Not critical",
        severity="low",
        source="scanner",
        evidence={}
    )
    assert mock_dispatch.call_count == 0


@patch("app.services.notification_dispatch_service.dispatch_notification")
def test_create_finding_dispatch_failure_does_not_rollback(mock_dispatch, db_session, repo_for_findings):
    mock_dispatch.side_effect = Exception("Simulated dispatch failure")
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
    assert mock_dispatch.call_count == 1
