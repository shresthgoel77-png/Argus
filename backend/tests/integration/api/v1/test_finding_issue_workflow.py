from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from app.integrations.github.exceptions import GitHubAuthError, GitHubNotFoundError
from app.models.finding import Finding
from app.models.repository_health_snapshot import RepositoryHealthSnapshot
from app.monitoring.monitor_service import run_analyzer
from app.services.finding_service import sync_findings_for_run
from app.monitoring.analyzer_base import FindingDraft


@pytest.fixture
def finding(db_session, test_user_repository):
    test_user_repository.monitoring_checks = {"security": {"status": "success"}}
    row = Finding(repository_id=test_user_repository.id, category='security',
        type='dependabot_alert_open', title='Vulnerable package', description='Advisory evidence',
        severity='high', status='open', source='on_demand:security',
        evidence={'manifest_path': 'requirements.txt', 'line': 7, 'github_alert_number': 1},
        fingerprint=f'security:{test_user_repository.id}:dependabot:1')
    db_session.add(row)
    db_session.commit()
    return row


@pytest.fixture
def github(monkeypatch):
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.list_repository_issues = AsyncMock(return_value=[])
    client.create_repository_issue = AsyncMock(return_value={
        'number': 8, 'title': 'Published finding', 'state': 'open',
        'html_url': 'https://github.com/test-org/test-repo/issues/8', 'labels': []})
    monkeypatch.setattr('app.services.finding_issue_service.GitHubAppClient', lambda *a, **k: client)
    return client


@pytest.mark.asyncio
async def test_preview_approval_idempotency_and_rescan(authorized_client, db_session, finding, github):
    path = f'/api/v1/findings/{finding.id}'
    preview = await authorized_client.get(path + '/issue-preview')
    assert preview.status_code == 200
    data = preview.json()
    assert 'requirements.txt' in data['body'] and '"line": 7' in data['body']
    github.create_repository_issue.assert_not_called()
    for payload in ({'preview_token': data['preview_token']}, {'preview_token': data['preview_token'], 'approved': False}):
        assert (await authorized_client.post(path + '/issue', json=payload)).status_code == 422
    payload = {'preview_token': data['preview_token'], 'approved': True}
    assert (await authorized_client.post(path + '/issue', json=payload)).status_code == 200
    assert (await authorized_client.post(path + '/issue', json=payload)).status_code == 200
    github.create_repository_issue.assert_awaited_once_with(finding.repository.full_name, title=data['title'], body=data['body'])
    sync_findings_for_run(db_session, repository_id=finding.repository_id, category='security', analyzer_key='security', drafts=[
        FindingDraft(category='security', type_=finding.type, title=finding.title, description=finding.description,
            severity='high', evidence={'manifest_path': 'requirements.txt', 'line': 7, 'github_alert_number': 1}, fingerprint=finding.fingerprint)])
    assert finding.evidence['_github_issue']['status'] == 'created'
    assert (await authorized_client.post(path + '/issue', json=payload)).status_code == 200
    assert github.create_repository_issue.await_count == 1


@pytest.mark.asyncio
async def test_stale_preview_and_unowned_finding_rejected(authorized_client, db_session, finding, github):
    path = f'/api/v1/findings/{finding.id}'
    token = (await authorized_client.get(path + '/issue-preview')).json()['preview_token']
    finding.severity = 'critical'
    db_session.commit()
    assert (await authorized_client.post(path + '/issue', json={'approved': True, 'preview_token': token})).status_code == 409
    owner = finding.repository.connection
    import uuid
    from app.models.user import User
    other = User(email=f'{uuid.uuid4()}@example.com', auth_provider='test')
    db_session.add(other)
    db_session.flush()
    owner.user_id = other.id
    db_session.commit()
    assert (await authorized_client.get(path + '/issue-preview')).status_code == 404
    assert (await authorized_client.post(path + '/issue', json={'approved': True, 'preview_token': token})).status_code == 404
    github.create_repository_issue.assert_not_called()


@pytest.mark.asyncio
async def test_ambiguous_github_result_never_reposts(authorized_client, finding, github):
    path = f'/api/v1/findings/{finding.id}'
    token = (await authorized_client.get(path + '/issue-preview')).json()['preview_token']
    github.create_repository_issue.side_effect = httpx.ReadTimeout('timed out')
    payload = {'approved': True, 'preview_token': token}
    assert (await authorized_client.post(path + '/issue', json=payload)).status_code == 502
    assert (await authorized_client.post(path + '/issue', json=payload)).status_code == 409
    assert github.create_repository_issue.await_count == 1
    # Reconcile an issue GitHub accepted before the connection timed out, including closed issues.
    github.list_repository_issues.return_value = [{**github.create_repository_issue.return_value,
        'body': f'<!-- repomedic-finding:{finding.id} -->', 'state': 'closed'}]
    assert (await authorized_client.post(path + '/issue', json=payload)).status_code == 200
    assert github.create_repository_issue.await_count == 1
    github.list_repository_issues.assert_awaited_with(finding.repository.full_name, state='all')


@pytest.mark.asyncio
async def test_github_permission_error_is_visible_and_retryable(authorized_client, finding, github):
    path = f'/api/v1/findings/{finding.id}'
    token = (await authorized_client.get(path + '/issue-preview')).json()['preview_token']
    github.create_repository_issue.side_effect = GitHubAuthError('Issues write permission required', response_status=403)
    response = await authorized_client.post(path + '/issue', json={'approved': True, 'preview_token': token})
    assert response.status_code in {401, 403}
    assert 'permission' in str(response.json())
    assert finding.evidence['_github_issue']['status'] == 'failed'


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [GitHubAuthError('denied'), GitHubNotFoundError('missing'), httpx.ReadTimeout('timeout')])
async def test_failed_scans_preserve_findings_and_health(db_session, test_user_repository, finding, monkeypatch, failure):
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.list_dependabot_alerts = AsyncMock(side_effect=failure)
    monkeypatch.setattr('app.monitoring.monitor_service.GitHubAppClient', lambda **k: client)
    before = db_session.query(RepositoryHealthSnapshot).count()
    result = await run_analyzer(db_session, 'security', test_user_repository)
    assert result.status == 'failed'
    db_session.refresh(finding)
    assert finding.status == 'open' and finding.severity == 'high'
    assert finding.evidence['line'] == 7
    assert db_session.query(RepositoryHealthSnapshot).count() == before


@pytest.mark.asyncio
async def test_verified_alert_persists_severity_evidence_and_health(db_session, test_user_repository, monkeypatch):
    test_user_repository.monitoring_checks = {k: {'status': 'success'} for k in
        ['ci_cd', 'stale_issues', 'stale_prs', 'dependency', 'security', 'code_quality']}
    db_session.commit()
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.list_dependabot_alerts = AsyncMock(return_value=[{'number': 1, 'state': 'open',
        'html_url': 'https://github.com/test-org/test-repo/security/dependabot/1',
        'security_advisory': {'summary': 'Verified advisory', 'severity': 'critical'},
        'dependency': {'package': {'name': 'vulnerable'}, 'manifest_path': 'package.json'}}])
    monkeypatch.setattr('app.monitoring.monitor_service.GitHubAppClient', lambda **k: client)
    assert (await run_analyzer(db_session, 'security', test_user_repository)).status == 'success'
    row = db_session.query(Finding).filter_by(repository_id=test_user_repository.id).one()
    assert row.severity == 'critical' and row.evidence['manifest_path'] == 'package.json'
    assert 'line' not in row.evidence  # Dependabot does not provide a source line.
    snapshot = db_session.query(RepositoryHealthSnapshot).filter_by(repository_id=test_user_repository.id).one()
    assert snapshot.overall_score < 100 and snapshot.category_scores['security'] < 100
    row.status = 'acknowledged'
    db_session.commit()
    assert (await run_analyzer(db_session, 'security', test_user_repository)).status == 'success'
    assert db_session.query(Finding).filter_by(repository_id=test_user_repository.id).count() == 1
    client.list_dependabot_alerts.return_value = []
    await run_analyzer(db_session, 'security', test_user_repository)
    db_session.refresh(row)
    assert row.status == 'resolved'


@pytest.mark.asyncio
async def test_public_status_filter(authorized_client, finding):
    for path in ['/api/v1/findings', f'/api/v1/repositories/{finding.repository_id}/findings']:
        assert (await authorized_client.get(path, params={'status': 'resolved'})).json()['total'] == 0
        assert (await authorized_client.get(path, params={'status': 'open'})).json()['total'] == 1

@pytest.mark.asyncio
async def test_malformed_scan_never_resolves_existing_finding(db_session, test_user_repository, finding, monkeypatch):
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.list_dependabot_alerts = AsyncMock(return_value=[{'number': 2, 'state': 'open'}])
    monkeypatch.setattr('app.monitoring.monitor_service.GitHubAppClient', lambda **k: client)
    assert (await run_analyzer(db_session, 'security', test_user_repository)).status == 'failed'
    db_session.refresh(finding)
    assert finding.status == 'open'
    assert db_session.query(Finding).filter_by(repository_id=test_user_repository.id).count() == 1


def test_sync_preserves_ignored_findings_and_other_analyzer_sources(db_session, finding):
    finding.status = 'ignored'
    db_session.commit()
    draft = FindingDraft(category=finding.category, type_=finding.type, title=finding.title,
        description=finding.description, severity=finding.severity, evidence={'github_alert_number': 1}, fingerprint=finding.fingerprint)
    result = sync_findings_for_run(db_session, repository_id=finding.repository_id, category='security', analyzer_key='security', drafts=[draft])
    assert result.skipped_ignored == 1
    assert db_session.query(Finding).filter_by(repository_id=finding.repository_id).count() == 1
    finding.status = 'open'
    finding.source = 'another_scanner:security'
    db_session.commit()
    sync_findings_for_run(db_session, repository_id=finding.repository_id, category='security', analyzer_key='security', drafts=[])
    assert finding.status == 'open'


@pytest.mark.asyncio
async def test_resolved_or_unverified_finding_cannot_generate_issue(authorized_client, db_session, finding, github):
    path = f'/api/v1/findings/{finding.id}/issue-preview'
    finding.status = 'resolved'
    db_session.commit()
    assert (await authorized_client.get(path)).status_code == 409
    finding.status = 'open'
    finding.evidence = {}
    db_session.commit()
    assert (await authorized_client.get(path)).status_code == 409
    github.create_repository_issue.assert_not_called()


def test_concurrent_open_fingerprint_conflict_keeps_session_usable(db_session, finding):
    from sqlalchemy.orm import Query
    from unittest.mock import patch
    from app.services.finding_service import create_finding
    # Model a stale pre-insert lookup while retaining the real unique constraint.
    original_first = Query.first
    calls = 0
    def stale_once(query):
        nonlocal calls
        calls += 1
        return None if calls == 1 else original_first(query)
    with patch.object(Query, 'first', stale_once):
        updated = create_finding(db_session, repository_id=finding.repository_id,
            category='security', type_=finding.type, title='Updated by concurrent run',
            description=finding.description, severity='critical', source=finding.source,
            evidence={'github_alert_number': 1}, fingerprint=finding.fingerprint)
    assert updated.id == finding.id and updated.severity == 'critical'
    assert db_session.query(Finding).filter_by(repository_id=finding.repository_id).count() == 1
