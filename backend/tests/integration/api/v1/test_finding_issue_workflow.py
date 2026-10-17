from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from app.integrations.github.exceptions import GitHubAuthError, GitHubNotFoundError
from app.models.finding import Finding
from app.models.repository_health_snapshot import RepositoryHealthSnapshot
from app.monitoring.monitor_service import run_analyzer
from app.services.finding_service import sync_findings_for_run
from app.monitoring.analyzer_base import FindingDraft


@pytest.fixture(autouse=True)
def email_delivery(monkeypatch):
    delivery = MagicMock()
    monkeypatch.setattr('app.services.finding_issue_service.send_issue_created_email', delivery)
    return delivery


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
async def test_stale_preview_and_unowned_finding_rejected(authorized_client, db_session, finding, github, email_delivery):
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
    email_delivery.assert_not_called()


@pytest.mark.asyncio
async def test_ambiguous_github_result_never_reposts(authorized_client, finding, github, email_delivery):
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
    email_delivery.assert_not_called()


@pytest.mark.asyncio
async def test_github_permission_error_is_visible_and_retryable(authorized_client, finding, github, email_delivery):
    path = f'/api/v1/findings/{finding.id}'
    token = (await authorized_client.get(path + '/issue-preview')).json()['preview_token']
    github.create_repository_issue.side_effect = GitHubAuthError('Issues write permission required', response_status=403)
    response = await authorized_client.post(path + '/issue', json={'approved': True, 'preview_token': token})
    assert response.status_code in {401, 403}
    assert 'permission' in str(response.json())
    assert finding.evidence['_github_issue']['status'] == 'failed'
    email_delivery.assert_not_called()


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


@pytest.mark.asyncio
async def test_new_issue_notifies_initiator_once_after_confirmation(
    authorized_client, finding, github, test_user, email_delivery,
):
    path = f'/api/v1/findings/{finding.id}'
    token = (await authorized_client.get(path + '/issue-preview')).json()['preview_token']
    payload = {'approved': True, 'preview_token': token}
    response = await authorized_client.post(path + '/issue', json=payload)
    assert response.status_code == 200
    assert response.json()['html_url'] == github.create_repository_issue.return_value['html_url']
    assert finding.evidence['_github_issue']['status'] == 'created'
    email_delivery.assert_called_once_with(
        user_id=str(test_user.id), recipient_email=test_user.email,
        auth_provider=test_user.auth_provider, external_id=test_user.external_auth_id,
        finding_id=str(finding.id), repository_name=finding.repository.full_name,
        issue_title='Published finding', issue_url=response.json()['html_url'],
        category='security', severity='high', description='Advisory evidence',
    )
    assert (await authorized_client.post(path + '/issue', json=payload)).status_code == 200
    email_delivery.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('missing', ['html_url', 'number'])
async def test_unconfirmed_issue_never_notifies(authorized_client, finding, github, email_delivery, missing):
    github.create_repository_issue.return_value.pop(missing)
    path = f'/api/v1/findings/{finding.id}'
    token = (await authorized_client.get(path + '/issue-preview')).json()['preview_token']
    response = await authorized_client.post(path + '/issue', json={'approved': True, 'preview_token': token})
    assert response.status_code == 502
    email_delivery.assert_not_called()


@pytest.mark.asyncio
async def test_email_scheduling_failure_preserves_issue_response(
    authorized_client, finding, github, email_delivery, monkeypatch,
):
    from fastapi import BackgroundTasks
    scheduler = MagicMock(side_effect=RuntimeError('smtp-secret'))
    logger = MagicMock()
    monkeypatch.setattr(BackgroundTasks, 'add_task', scheduler)
    monkeypatch.setattr('app.services.finding_issue_service.logger', logger)
    path = f'/api/v1/findings/{finding.id}'
    token = (await authorized_client.get(path + '/issue-preview')).json()['preview_token']
    response = await authorized_client.post(path + '/issue', json={'approved': True, 'preview_token': token})
    assert response.status_code == 200
    assert response.json()['html_url'] == github.create_repository_issue.return_value['html_url']
    assert finding.evidence['_github_issue']['status'] == 'created'
    email_delivery.assert_not_called()
    scheduler.assert_called_once()
    logger.warning.assert_called_once_with('Issue email scheduling failed')


@pytest.mark.asyncio
@pytest.mark.parametrize('result', ['success', 'exception', 'failure'])
async def test_http_response_is_sent_while_email_delivery_is_blocked(
    authorized_client, db_session, finding, github, test_user, monkeypatch, result,
):
    import asyncio
    import json
    import threading
    from types import SimpleNamespace
    from pydantic import SecretStr
    from app.main import app
    from app.services import issue_notification_service as mail

    test_user.auth_provider = 'clerk'
    test_user.external_auth_id = 'user_initiator'
    db_session.commit()
    for name, value in {
        'smtp_host': 'smtp.example.com', 'smtp_username': 'sender',
        'smtp_password': SecretStr('smtp-secret'), 'clerk_secret_key': SecretStr('clerk-secret'),
    }.items():
        monkeypatch.setattr(mail.settings, name, value)
    clerk = MagicMock()
    clerk.users.get.return_value = SimpleNamespace(id='user_initiator', email_addresses=[
        SimpleNamespace(email_address=test_user.email, verification=SimpleNamespace(status='verified')),
    ])
    monkeypatch.setattr(mail, 'Clerk', MagicMock(return_value=clerk))
    monkeypatch.setattr(mail, 'SessionLocal', MagicMock(side_effect=RuntimeError('No saved AI summary')))
    monkeypatch.setattr('app.services.finding_issue_service.send_issue_created_email', mail.send_issue_created_email)
    started, release = threading.Event(), threading.Event()
    provider = MagicMock()

    def deliver(**kwargs):
        started.set()
        release.wait(timeout=5)
        if result == 'exception':
            raise RuntimeError('smtp-secret')
        return SimpleNamespace(success=result == 'success')

    provider.send.side_effect = deliver
    monkeypatch.setattr(mail, 'get_provider', MagicMock(return_value=MagicMock(return_value=provider)))
    path = f'/api/v1/findings/{finding.id}'
    token = (await authorized_client.get(path + '/issue-preview')).json()['preview_token']
    path += '/issue'
    body = json.dumps({'approved': True, 'preview_token': token}).encode()
    scope = {
        'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
        'method': 'POST', 'scheme': 'http', 'path': path, 'raw_path': path.encode(),
        'query_string': b'', 'root_path': '', 'server': ('test', 80), 'client': ('127.0.0.1', 1234),
        'headers': [(b'content-type', b'application/json'), (b'content-length', str(len(body)).encode())],
    }
    messages, response_sent = [], asyncio.Event()
    received = False

    async def receive():
        nonlocal received
        if not received:
            received = True
            return {'type': 'http.request', 'body': body, 'more_body': False}
        await asyncio.Event().wait()

    async def send(message):
        messages.append(message)
        if message['type'] == 'http.response.body' and not message.get('more_body', False):
            response_sent.set()

    request_task = asyncio.create_task(app(scope, receive, send))
    try:
        await asyncio.wait_for(response_sent.wait(), timeout=3)
        assert await asyncio.to_thread(started.wait, 2)
        assert not release.is_set()
        assert not request_task.done()  # Email is still held after the full HTTP response.
        assert next(m for m in messages if m['type'] == 'http.response.start')['status'] == 200
        response_body = b''.join(m.get('body', b'') for m in messages if m['type'] == 'http.response.body')
        assert json.loads(response_body)['html_url'] == github.create_repository_issue.return_value['html_url']
    finally:
        release.set()
        await asyncio.wait_for(request_task, timeout=3)
    assert finding.evidence['_github_issue']['status'] == 'created'
    assert provider.send.call_args.kwargs['to'] == test_user.email
