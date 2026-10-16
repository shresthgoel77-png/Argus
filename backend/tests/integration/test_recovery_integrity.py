"""Regression checks use only disposable database records and mocked GitHub calls."""
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import uuid

import httpx
import pytest
from fastapi import HTTPException
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.integrations.github.client import GitHubAppClient
from app.integrations.github.exceptions import GitHubAPIError, GitHubInstallationError, GitHubNotFoundError
from app.integrations.github.install_state import generate_install_state
from app.models.finding import Finding
from app.models.github_connection import GitHubConnection
from app.models.repository_health_snapshot import RepositoryHealthSnapshot
from app.services.github_connection_service import upsert_connection_from_installation, verify_new_installation_account
from app.services.repository_service import add_repository
from app.services.finding_issue_service import preview_issue
from app.services.scheduled_monitoring_service import run_monitoring_checks_for_repository
from app.monitoring.analyzers.issue_analyzer import IssueAnalyzer
from app.monitoring.analyzers.pull_request_analyzer import PullRequestAnalyzer


def github_client(repo):
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.get_installation = AsyncMock(return_value={
        "id": 987001, "app_id": int(settings.github_app_id),
        "account": {"id": 42, "login": "test-org", "type": "Organization"},
        "permissions": {k: "write" for k in ["issues", "pull_requests", "contents", "actions", "administration", "vulnerability_alerts"]},
    })
    client.list_installation_repositories = AsyncMock(return_value=[{
        "id": repo.github_repo_id, "full_name": repo.full_name, "private": False, "default_branch": "main"}])
    client.list_repository_issues = AsyncMock(return_value=[])
    client.list_repository_pulls = AsyncMock(return_value=[])
    return client


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["missing", "wrong_app", "wrong_account", "permission", "repository", "suspended"])
async def test_reconnect_rejects_invalid_target_without_mutating_records(db_session, test_user, test_user_repository, failure):
    repo = test_user_repository
    conn = repo.connection
    before = (conn.id, conn.installation_id, conn.user_id, repo.id, repo.connection_id)
    client = github_client(repo)
    metadata = client.get_installation.return_value
    if failure == "missing": client.get_installation.side_effect = GitHubInstallationError(987001)
    if failure == "wrong_app": metadata["app_id"] = 9999999
    if failure == "wrong_account": metadata["account"]["login"] = "another-account"
    if failure == "permission": metadata["permissions"]["issues"] = "read"
    if failure == "repository": client.list_installation_repositories.return_value = []
    if failure == "suspended": metadata["suspended_at"] = "2026-01-01T00:00:00Z"
    with pytest.raises((HTTPException, GitHubInstallationError)):
        await upsert_connection_from_installation(db_session, test_user.id, 987001, client, reconnect_connection_id=conn.id)
    db_session.expire_all()
    assert (conn.id, conn.installation_id, conn.user_id, repo.id, repo.connection_id) == before
    assert db_session.query(GitHubConnection).filter_by(user_id=test_user.id).count() == 1


@pytest.mark.asyncio
async def test_reconnect_preserves_connection_repository_and_history_ids(authorized_client, db_session, test_user, test_user_repository, monkeypatch):
    repo = test_user_repository
    conn = repo.connection
    client = github_client(repo)
    monkeypatch.setattr("app.api.v1.github.GitHubAppClient", lambda **kwargs: client)
    before = (conn.id, conn.user_id, repo.id, repo.connection_id)
    start = await authorized_client.get("/api/v1/github/install/start", params={"connection_id": str(conn.id)})
    assert start.status_code == 200
    state = start.json()["install_url"].split("?state=")[1]
    response = await authorized_client.get("/api/v1/github/install/callback", params={"installation_id": "987001", "setup_action": "install", "state": state})
    assert response.status_code == 200
    db_session.refresh(conn)
    assert conn.installation_id == 987001
    assert (conn.id, conn.user_id, repo.id, repo.connection_id) == before
    client.list_installation_repositories.assert_awaited_once()


@pytest.mark.asyncio
async def test_unowned_reconnect_start_and_callback_rejected(authorized_client, test_user):
    missing = uuid.uuid4()
    assert (await authorized_client.get("/api/v1/github/install/start", params={"connection_id": str(missing)})).status_code == 404
    response = await authorized_client.get("/api/v1/github/install/callback", params={"installation_id": "987001", "setup_action": "install", "state": generate_install_state(test_user.id, missing)})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rebind_checks_access_before_changing_existing_association(db_session, test_user, test_user_repository):
    repo = test_user_repository
    old_id = repo.connection_id
    conn = GitHubConnection(user_id=test_user.id, installation_id=987001, account_login="test-org", account_type="Organization")
    db_session.add(conn); db_session.commit()
    client = github_client(repo)
    client.list_installation_repositories.return_value = []
    with pytest.raises(NotFoundError):
        await add_repository(db_session, conn, repo.github_repo_id, client)
    db_session.refresh(repo)
    assert repo.connection_id == old_id
    client.list_installation_repositories.assert_awaited_once()


@pytest.mark.asyncio
async def test_new_account_requires_verified_clerk_github_identity(monkeypatch):
    user = SimpleNamespace(auth_provider="clerk", external_auth_id="user_fixture")
    external = SimpleNamespace(provider="oauth_github", provider_user_id="42", verification=SimpleNamespace(status="verified"))
    clerk = MagicMock()
    clerk.users.get.return_value = SimpleNamespace(external_accounts=[external])
    monkeypatch.setattr("app.services.github_connection_service.Clerk", lambda **kwargs: clerk)
    monkeypatch.setattr(settings, "clerk_secret_key", __import__("pydantic").SecretStr("fixture-only"))
    await verify_new_installation_account(user, {"id": 42, "type": "User"})
    for account in ({"id": 43, "type": "User"}, {"id": 42, "type": "Organization"}):
        with pytest.raises(HTTPException) as error:
            await verify_new_installation_account(user, account)
        assert error.value.status_code == 403
    external.verification.status = "unverified"
    with pytest.raises(HTTPException):
        await verify_new_installation_account(user, {"id": 42, "type": "User"})


@pytest.mark.parametrize("assessment", [None, {}, {"status": "pending"}, {"status": "failed"}, {"status": "unavailable"}])
@pytest.mark.parametrize("source", ["on_demand:security", "webhook:push", "repository_scan:security"])
def test_preview_requires_successful_relevant_assessment(test_user_repository, assessment, source):
    repo = test_user_repository
    repo.monitoring_checks = {"security": assessment} if assessment is not None else {}
    finding = SimpleNamespace(repository=repo, category="security", status="open", source=source, evidence={"manifest_path": "requirements.txt", "github_alert_number": 1})
    with pytest.raises(HTTPException) as error:
        preview_issue(finding)
    assert error.value.status_code == 409


def test_preview_rejects_nonidentifying_evidence(test_user_repository):
    test_user_repository.monitoring_checks = {"security": {"status": "success"}}
    finding = SimpleNamespace(type="dependabot_alert_open", repository=test_user_repository, category="security", status="open", source="on_demand:security", evidence={"line": 7})
    with pytest.raises(HTTPException, match="identifiable source"):
        preview_issue(finding)


@pytest.mark.asyncio
@pytest.mark.parametrize("run", [
    {"id": 10, "workflow_id": 1, "status": "completed"},
    {"id": 10, "workflow_id": 1, "status": "completed", "conclusion": None},
    {"id": 10, "workflow_id": 1, "status": "completed", "conclusion": "unknown"},
    {"workflow_id": 1, "status": "completed", "conclusion": "success"},
    {"id": 10, "status": "completed", "conclusion": "success"},
    {"id": 10, "workflow_id": 1, "status": "in_progress", "conclusion": None},
])
async def test_incomplete_ci_preserves_findings_and_health(db_session, test_user_repository, monkeypatch, run):
    repo = test_user_repository
    finding = Finding(repository_id=repo.id, category="ci", type="workflow_run_failure", title="Failure", description="Failure", severity="high", source="on_demand:ci", evidence={"run_id": 9}, fingerprint="ci-9")
    snapshot = RepositoryHealthSnapshot(repository_id=repo.id, overall_score=80, category_scores={"ci_cd": 80}, reasons=["Existing"])
    db_session.add_all([finding, snapshot]); db_session.commit()
    client = github_client(repo)
    client.list_repository_workflow_runs = AsyncMock(return_value=[run])
    monkeypatch.setattr("app.services.scheduled_monitoring_service.GitHubAppClient", lambda *args: client)
    monkeypatch.setattr("app.services.scheduled_monitoring_service.run_analyzer", AsyncMock(return_value=SimpleNamespace(status="success")))
    result = await run_monitoring_checks_for_repository(db_session, repo)
    assert result.checks["ci_cd"].status == "unavailable"
    db_session.refresh(finding)
    assert finding.status == "open" and finding.severity == "high"
    assert db_session.query(RepositoryHealthSnapshot).filter_by(repository_id=repo.id).count() == 1
    assert snapshot.overall_score == 80


@pytest.mark.asyncio
@pytest.mark.parametrize("category,analyzer,method,listmethod,numberkey", [
    ("issue", IssueAnalyzer, "scan_repository_for_stale_issues", "list_repository_issues", "issue_number"),
    ("pull_request", PullRequestAnalyzer, "scan_repository_for_stale_prs", "list_repository_pulls", "pull_request_number"),
])
async def test_complete_stale_scan_reconciles_only_its_own_findings(db_session, test_user_repository, category, analyzer, method, listmethod, numberkey):
    repo = test_user_repository
    scan = Finding(repository_id=repo.id, category=category, type="stale_"+category, title="Stale", description="Stale", severity="info", source="repository_scan:"+category, evidence={numberkey: 1}, fingerprint="stale_"+category+"_1")
    webhook = Finding(repository_id=repo.id, category=category, type="opened_without_description", title="Webhook", description="Webhook", severity="info", source="webhook:"+category, evidence={numberkey: 2}, fingerprint="webhook-2")
    db_session.add_all([scan, webhook]); db_session.commit()
    client = github_client(repo)
    getattr(client, listmethod).return_value = [{"number": 3, "updated_at": (datetime.now(timezone.utc)-timedelta(days=60)).isoformat(), "html_url": "https://github.com/test-org/test-repo/issues/3"}, {"number": 4}]
    with pytest.raises(ValueError): await getattr(analyzer(), method)(db_session, repo, client)
    assert db_session.query(Finding).filter_by(repository_id=repo.id).count() == 2
    assert scan.status == "open"
    getattr(client, listmethod).return_value = []
    await getattr(analyzer(), method)(db_session, repo, client)
    db_session.refresh(scan); db_session.refresh(webhook)
    assert scan.status == "resolved"
    assert webhook.status == "open"


@pytest.mark.asyncio
async def test_installation_failure_is_not_repository_404():
    async with GitHubAppClient(123) as client:
        client._auth_headers = AsyncMock(side_effect=GitHubNotFoundError(response_status=404))
        with pytest.raises(GitHubInstallationError) as error:
            await client.list_repository_issues("owner/repo")
        assert error.value.status_code == 409
        assert error.value.code == "github_installation_unavailable"


@pytest.mark.parametrize("status,expected,code", [(401, 502, "github_auth_error"), (403, 403, "github_permission_error"), (404, 404, "github_not_found")])
def test_upstream_error_mapping_does_not_impersonate_clerk(status, expected, code):
    error = GitHubAPIError.from_response(httpx.Response(status, json={"message": "sanitized fixture"}))
    assert error.status_code == expected and error.code == code


def test_failed_reconciliation_rolls_back_all_resolutions(db_session, test_user_repository, monkeypatch):
    from app.services import finding_lifecycle_service, finding_service
    rows = [Finding(repository_id=test_user_repository.id, category="security", type="dependabot_alert_open", title="Evidence", description="Evidence", severity="high", source="on_demand:security", evidence={"github_alert_number": n}, fingerprint=f"atomic-{n}") for n in [1, 2]]
    db_session.add_all(rows); db_session.commit()
    real_resolve = finding_lifecycle_service.auto_resolve_finding
    calls = 0
    def fail_second(db, finding, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2: raise RuntimeError("simulated persistence failure")
        return real_resolve(db, finding, **kwargs)
    monkeypatch.setattr(finding_lifecycle_service, "auto_resolve_finding", fail_second)
    with pytest.raises(RuntimeError):
        finding_service.sync_findings_for_run(db_session, repository_id=test_user_repository.id, category="security", analyzer_key="security", drafts=[])
    db_session.expire_all()
    assert {row.status for row in rows} == {"open"}


@pytest.mark.parametrize("source,type_,evidence", [
    ("webhook:push", "dependabot_alert_open", {"github_alert_number": 1, "manifest_path": "requirements.txt"}),
    ("on_demand:security", "unassessed_condition", {"github_alert_number": 1, "manifest_path": "requirements.txt"}),
    ("on_demand:security", "dependabot_alert_open", {"manifest_path": "requirements.txt"}),
    ("on_demand:security", "dependabot_alert_open", {"github_alert_number": 1}),
])
def test_successful_assessment_alone_does_not_verify_unassessed_evidence(test_user_repository, source, type_, evidence):
    test_user_repository.monitoring_checks = {"security": {"status": "success"}}
    finding = SimpleNamespace(type=type_, repository=test_user_repository, category="security", status="open", source=source, evidence=evidence)
    with pytest.raises(HTTPException) as error:
        preview_issue(finding)
    assert error.value.status_code == 409
