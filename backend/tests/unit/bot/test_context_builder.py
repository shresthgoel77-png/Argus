import uuid

import pytest

from app.bot.context_builder import build_bot_context
from app.bot.question_parser import BotIntent
from app.integrations.github.webhook_events import NormalizedWebhookEvent, RepoRef
from app.models.finding import Finding
from app.models.repository_health_snapshot import RepositoryHealthSnapshot
from app.services.ai_context_builder import build_context


def event(payload):
    return NormalizedWebhookEvent(
        delivery_id="delivery",
        event_type="issue_comment",
        action="created",
        installation_id=123456,
        repository=RepoRef(1, "test-org/test-repo"),
        installation_account_login=None,
        installation_account_type=None,
        repositories_removed=[],
        raw_payload=payload,
    )


def add_finding(db_session, repository, category, evidence, *, severity="high"):
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
    )
    db_session.add(finding)
    db_session.commit()
    return finding


@pytest.mark.asyncio
async def test_ci_status_uses_existing_finding(db_session, test_user_repository):
    add_finding(db_session, test_user_repository, "ci_cd", {"log_excerpt": "failure"})

    context = await build_bot_context(BotIntent.ci_status, test_user_repository, event({}))

    assert context.source == "finding"
    assert "Log Excerpt:\nfailure" in context.untrusted_content


@pytest.mark.asyncio
async def test_ci_status_without_finding_is_static(db_session, test_user_repository):
    context = await build_bot_context(BotIntent.ci_status, test_user_repository, event({}))

    assert context.static_response == "No known CI failures are recorded for this repository."
    assert context.source == "database"


@pytest.mark.asyncio
async def test_pr_summary_falls_back_to_one_github_read(
    db_session, test_user_repository, monkeypatch
):
    calls = []

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get_pull_request(self, full_name, number):
            calls.append((full_name, number))
            return {"title": "Fix", "body": "Details", "changed_files": 3}

    monkeypatch.setattr("app.bot.context_builder.GitHubAppClient", lambda _: Client())
    context = await build_bot_context(
        BotIntent.pr_summary,
        test_user_repository,
        event({"issue": {"number": 7, "pull_request": {}}}),
    )

    assert calls == [("test-org/test-repo", 7)]
    assert context.source == "github"
    assert "PR Description:\nDetails" in context.untrusted_content


@pytest.mark.asyncio
async def test_issue_explain_falls_back_to_one_github_read(
    db_session, test_user_repository, monkeypatch
):
    calls = []

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get_issue(self, full_name, number):
            calls.append((full_name, number))
            return {"title": "Crash", "body": "Trace", "labels": [], "comments": 2}

    monkeypatch.setattr("app.bot.context_builder.GitHubAppClient", lambda _: Client())
    context = await build_bot_context(
        BotIntent.issue_explain,
        test_user_repository,
        event({"issue": {"number": 8}}),
    )

    assert calls == [("test-org/test-repo", 8)]
    assert "Issue Description:\nTrace" in context.untrusted_content


@pytest.mark.asyncio
async def test_repo_attention_aggregates_findings_and_latest_reasons(
    db_session, test_user_repository
):
    add_finding(db_session, test_user_repository, "security", {}, severity="critical")
    snapshot = RepositoryHealthSnapshot(
        repository_id=test_user_repository.id,
        overall_score=50,
        category_scores={"security": 20},
        reasons=["Security needs attention."],
    )
    db_session.add(snapshot)
    db_session.commit()

    context = await build_bot_context(BotIntent.repo_attention, test_user_repository, event({}))

    assert "[critical] Test finding" in context.untrusted_content
    assert "Security needs attention." in context.untrusted_content


@pytest.mark.asyncio
async def test_bot_and_finding_context_share_delimiter_output(
    db_session, test_user_repository
):
    finding = add_finding(
        db_session,
        test_user_repository,
        "pull_requests",
        {"pr_title": "Fix", "description": "Details", "file_changes": 2},
    )
    finding_context = build_context(finding)
    bot_context = await build_bot_context(
        BotIntent.pr_summary,
        test_user_repository,
        event({"pull_request": {"number": 4}}),
    )

    assert bot_context.untrusted_content == finding_context.untrusted_content