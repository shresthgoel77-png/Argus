from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import SecretStr

from app.services import issue_notification_service as service


@pytest.fixture
def mail(monkeypatch):
    for name, value in {
        "smtp_host": "smtp.example.com", "smtp_username": "smtp-user",
        "smtp_password": SecretStr("smtp-secret"), "smtp_from_address": "bot@example.com",
        "smtp_port": 587, "smtp_use_tls": True,
        "clerk_secret_key": SecretStr("clerk-secret"),
    }.items():
        monkeypatch.setattr(service.settings, name, value)
    clerk = MagicMock()
    clerk.users.get.return_value = SimpleNamespace(id="user_initiator", email_addresses=[
        SimpleNamespace(email_address="owner@example.com", verification=SimpleNamespace(status="verified")),
        SimpleNamespace(email_address="initiator@example.com", verification=SimpleNamespace(status="verified")),
    ])
    monkeypatch.setattr(service, "Clerk", MagicMock(return_value=clerk))
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = SimpleNamespace(
        summary='<script>AI & summary</script>',
    )
    monkeypatch.setattr(service, "SessionLocal", MagicMock(return_value=db))
    db.__enter__.return_value = db
    smtp = MagicMock()
    monkeypatch.setattr("app.integrations.email.smtp_provider.smtplib.SMTP", smtp)
    return SimpleNamespace(clerk=clerk, db=db, smtp=smtp)


@pytest.fixture
def payload():
    return dict(
        user_id=str(uuid4()), recipient_email="initiator@example.com", auth_provider="clerk",
        external_id="user_initiator", finding_id=str(uuid4()),
        repository_name='org/repo <&"', issue_title='Issue <&"',
        issue_url='https://github.com/org/repo/issues/8?x=1&y="2"',
        category="security <&", severity="high", description='<img src=x onerror=alert(1)>\nDetails & more',
    )


def test_smtp_delivery_has_verified_initiator_escaped_content_and_link(mail, payload):
    service.send_issue_created_email(**payload)
    mail.clerk.users.get.assert_called_once_with(user_id="user_initiator")
    smtp = mail.smtp.return_value
    smtp.send_message.assert_called_once()
    message = smtp.send_message.call_args.args[0]
    assert message["To"] == "initiator@example.com"
    assert message["From"] == "bot@example.com"
    assert message["Subject"] == 'RepoMedic issue created: Issue <&"'
    plain, html = [part.get_payload(decode=True).decode(part.get_content_charset())
                   for part in message.get_payload()]
    assert 'org/repo <&"' in plain and payload["issue_url"] in plain
    assert "Repository:</strong> org/repo &lt;&amp;&quot;" in html
    assert "Issue title:</strong> Issue &lt;&amp;&quot;" in html
    assert "Category:</strong> security &lt;&amp;" in html
    assert "Severity:</strong> high" in html
    assert "&lt;img src=x onerror=alert(1)&gt;<br>Details &amp; more" in html
    assert "&lt;script&gt;AI &amp; summary&lt;/script&gt;" in html
    assert '<a href="https://github.com/org/repo/issues/8?x=1&amp;y=&quot;2&quot;">' in html
    assert "<script>" not in html and "<img" not in html


@pytest.mark.parametrize("missing", ["smtp_host", "smtp_username", "smtp_password", "clerk_secret_key"])
def test_missing_configuration_skips_without_external_calls(mail, payload, monkeypatch, missing):
    monkeypatch.setattr(service.settings, missing, None)
    service.send_issue_created_email(**payload)
    mail.clerk.users.get.assert_not_called()
    mail.smtp.assert_not_called()


@pytest.mark.parametrize("field,value", [
    ("recipient_email", None), ("recipient_email", "unregistered@example.com"),
    ("external_id", None), ("auth_provider", "unknown"),
])
def test_missing_or_unregistered_identity_never_uses_owner_email(mail, payload, field, value):
    payload[field] = value
    service.send_issue_created_email(**payload)
    mail.smtp.assert_not_called()


@pytest.mark.parametrize("status", ["unverified", "failed", None])
def test_unverified_address_is_not_notified(mail, payload, status):
    mail.clerk.users.get.return_value.email_addresses[1].verification.status = status
    service.send_issue_created_email(**payload)
    mail.smtp.assert_not_called()


def test_wrong_clerk_identity_skips(mail, payload):
    mail.clerk.users.get.return_value.id = "another-user"
    service.send_issue_created_email(**payload)
    mail.smtp.assert_not_called()


@pytest.mark.parametrize("url", ["javascript:alert(1)", "https://github.com.evil.test/issues/8", "https://secret@github.com/issues/8"])
def test_untrusted_link_is_not_emailed(mail, payload, url):
    payload["issue_url"] = url
    service.send_issue_created_email(**payload)
    mail.smtp.assert_not_called()


def test_missing_optional_content_is_omitted(mail, payload):
    payload.update(category=None, severity=None, description=None)
    mail.db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    service.send_issue_created_email(**payload)
    message = mail.smtp.return_value.send_message.call_args.args[0]
    text = message.get_payload()[0].get_payload(decode=True).decode()
    for label in ["Category:", "Severity:", "Description:", "AI summary:"]:
        assert label not in text
    assert "None" not in text


@pytest.mark.parametrize("stage", ["clerk", "summary", "smtp", "provider"])
def test_failures_are_contained_and_logs_do_not_expose_details(mail, payload, monkeypatch, stage):
    logger = MagicMock()
    monkeypatch.setattr(service, "logger", logger)
    failure = RuntimeError("smtp-secret initiator@example.com private-body")
    if stage == "clerk":
        mail.clerk.users.get.side_effect = failure
    elif stage == "summary":
        mail.db.query.side_effect = failure
    elif stage == "smtp":
        mail.smtp.side_effect = failure
    else:
        monkeypatch.setattr(service, "get_provider", MagicMock(side_effect=failure))
    service.send_issue_created_email(**payload)
    logger.warning.assert_called_once()
    logged = repr(logger.warning.call_args)
    assert "failed" in logged
    assert "smtp-secret" not in logged
    assert "initiator@example.com" not in logged
    assert "private-body" not in logged
    assert "exc_info" not in logged
    if stage == "summary":
        mail.smtp.return_value.send_message.assert_called_once()


def test_only_saved_completed_summary_for_this_finding_is_used(
    mail, payload, db_session, test_user_repository, monkeypatch,
):
    from contextlib import nullcontext
    from datetime import datetime, timedelta, timezone
    from app.models.ai_analysis import AIAnalysis
    from app.models.finding import Finding

    finding = Finding(
        repository_id=test_user_repository.id, category="security", type="test",
        title="Finding", description="Description", severity="high", status="open",
        source="test", evidence={}, fingerprint=str(uuid4()),
    )
    db_session.add(finding)
    db_session.flush()
    now = datetime.now(timezone.utc)
    db_session.add_all([
        AIAnalysis(finding_id=finding.id, status="completed", provider="test", model="test",
                   summary="Saved completed explanation", requested_at=now - timedelta(days=1)),
        AIAnalysis(finding_id=finding.id, status="failed", provider="test", model="test",
                   summary="Do not include failed content", requested_at=now),
        AIAnalysis(repository_id=test_user_repository.id, status="completed", provider="test", model="test",
                   summary="Do not include repository summary", requested_at=now),
    ])
    db_session.commit()
    payload["finding_id"] = str(finding.id)
    monkeypatch.setattr(service, "SessionLocal", lambda: nullcontext(db_session))
    service.send_issue_created_email(**payload)
    text = mail.smtp.return_value.send_message.call_args.args[0].get_payload()[0].get_payload(decode=True).decode()
    assert "AI summary: Saved completed explanation" in text
    assert "Do not include" not in text
