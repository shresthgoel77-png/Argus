"""Integration-style tests for bot_orchestration_service.handle_mention.

All external calls (GitHub client, AI provider, ai_connection_service) are
mocked.  Each test verifies BotInteraction persistence and call-ordering
guarantees specified by Prompt 7.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.bot.bot_orchestration_service import handle_mention, _STATIC_HELP_REPLY
from app.bot.context_builder import BotContext
from app.bot.question_parser import BotIntent
from app.integrations.ai.provider_base import BotResponseResult
from app.integrations.github.client import PostedComment
from app.integrations.github.webhook_events import NormalizedWebhookEvent, RepoRef
from app.models.bot_interaction import BotInteraction
from app.models.github_event import GitHubEvent
from app.models.ai_connection import AIConnection
from app.core.encryption import encrypt_secret
from app.services.ai_context_common import SYSTEM_INSTRUCTIONS_BLOCK, wrap_untrusted_content


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(db, delivery_id="delivery-orch-1"):
    event = GitHubEvent(
        delivery_id=delivery_id,
        event_type="issue_comment",
        action="created",
        payload={},
    )
    db.add(event)
    db.flush()
    return event


def _make_normalized(
    delivery_id="delivery-orch-1",
    comment_body="@repomedic explain this issue",
    commenter_login="octocat",
    issue_number=42,
    has_pull_request=False,
):
    issue = {"number": issue_number}
    if has_pull_request:
        issue["pull_request"] = {"url": "https://api.github.com/repos/org/repo/pulls/42"}
    return NormalizedWebhookEvent(
        delivery_id=delivery_id,
        event_type="issue_comment",
        action="created",
        installation_id=123456,
        repository=RepoRef(github_repo_id=12345, full_name="test-org/test-repo"),
        installation_account_login="test-org",
        installation_account_type="Organization",
        repositories_removed=[],
        raw_payload={
            "action": "created",
            "comment": {
                "body": comment_body,
                "user": {"login": commenter_login},
            },
            "issue": issue,
            "installation": {"id": 123456},
        },
    )


def _mock_github_client(permission="write", post_comment_id=99999):
    """Return (context_manager, client_instance)."""
    client = MagicMock()
    client.get_collaborator_permission = AsyncMock(return_value=permission)
    posted = PostedComment(id=post_comment_id)
    client.post_issue_comment = AsyncMock(return_value=posted)
    client.get_issue = AsyncMock(return_value={"title": "Bug", "body": "desc", "labels": [], "comments": 2})
    client.get_pull_request = AsyncMock(return_value={"title": "PR", "body": "desc", "changed_files": 3})
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx, client


def _setup_ai_connection(db, user_id):
    """Seed an AIConnection row for the user."""
    conn = AIConnection(
        user_id=user_id,
        provider="gemini",
        model="gemini-3.8-flash",
        encrypted_api_key=encrypt_secret("fake-api-key-for-test"),
        status="valid",
    )
    db.add(conn)
    db.commit()
    return conn


def _fake_bot_context(intent=BotIntent.issue_explain):
    return BotContext(
        intent=intent,
        system_instructions=SYSTEM_INSTRUCTIONS_BLOCK,
        untrusted_content=wrap_untrusted_content("test content"),
        source="test",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_mention_no_interaction(db_session, test_user_repository):
    """extract_mention returns None → no BotInteraction row created."""
    event = _make_event(db_session, "no-mention-1")
    normalized = _make_normalized(
        delivery_id="no-mention-1",
        comment_body="just a regular comment with no bot mention",
    )

    await handle_mention(db_session, event, test_user_repository, normalized)

    count = db_session.query(BotInteraction).count()
    assert count == 0


@pytest.mark.asyncio
async def test_unknown_intent_posts_help(db_session, test_user_repository):
    """Unknown intent with write permission → static help reply, BotInteraction(status=completed, intent=unknown)."""
    event = _make_event(db_session, "unknown-help-1")
    normalized = _make_normalized(
        delivery_id="unknown-help-1",
        comment_body="@repomedic do something weird",
    )

    ctx, client = _mock_github_client(permission="write", post_comment_id=7777)

    with patch("app.bot.bot_orchestration_service.GitHubAppClient", return_value=ctx):
        await handle_mention(db_session, event, test_user_repository, normalized)

    interaction = db_session.query(BotInteraction).filter_by(github_event_id=event.id).one()
    assert interaction.status == "completed"
    assert interaction.intent == "unknown"
    assert interaction.response_text == _STATIC_HELP_REPLY
    assert interaction.github_reply_comment_id == 7777

    # Verify post_issue_comment was called
    client.post_issue_comment.assert_awaited_once()


@pytest.mark.asyncio
async def test_unknown_intent_insufficient_permission_silent(db_session, test_user_repository):
    """Unknown intent with read permission → no GitHub post, BotInteraction(status=skipped)."""
    event = _make_event(db_session, "unknown-noperm-1")
    normalized = _make_normalized(
        delivery_id="unknown-noperm-1",
        comment_body="@repomedic do something weird",
    )

    ctx, client = _mock_github_client(permission="read")

    with patch("app.bot.bot_orchestration_service.GitHubAppClient", return_value=ctx):
        await handle_mention(db_session, event, test_user_repository, normalized)

    interaction = db_session.query(BotInteraction).filter_by(github_event_id=event.id).one()
    assert interaction.status == "skipped"
    assert interaction.intent == "unknown"
    assert interaction.skip_reason == "insufficient_permission"

    # No GitHub post
    client.post_issue_comment.assert_not_awaited()


@pytest.mark.asyncio
async def test_authorization_denied_no_ai_no_post(db_session, test_user_repository):
    """authorize_mention denies → no AI call, no GitHub post, BotInteraction(status=skipped)."""
    event = _make_event(db_session, "auth-denied-1")
    normalized = _make_normalized(
        delivery_id="auth-denied-1",
        comment_body="@repomedic explain this issue",
    )

    mock_auth_result = MagicMock()
    mock_auth_result.authorized = False
    mock_auth_result.skip_reason = "ai_not_configured"

    mock_provider_cls = MagicMock()
    ctx, client = _mock_github_client()

    with patch("app.bot.bot_orchestration_service.authorize_mention", new_callable=AsyncMock, return_value=mock_auth_result), \
         patch("app.bot.bot_orchestration_service.GitHubAppClient", return_value=ctx), \
         patch("app.bot.bot_orchestration_service.get_provider", return_value=mock_provider_cls):
        await handle_mention(db_session, event, test_user_repository, normalized)

    interaction = db_session.query(BotInteraction).filter_by(github_event_id=event.id).one()
    assert interaction.status == "skipped"
    assert interaction.skip_reason == "ai_not_configured"

    # No AI call
    mock_provider_cls.assert_not_called()
    # No GitHub post
    client.post_issue_comment.assert_not_awaited()


@pytest.mark.asyncio
async def test_happy_path_end_to_end(db_session, test_user_repository, test_user):
    """Full flow: mention → authorized → context → AI → comment → BotInteraction(completed)."""
    event = _make_event(db_session, "happy-1")
    normalized = _make_normalized(
        delivery_id="happy-1",
        comment_body="@repomedic explain this issue",
        issue_number=10,
    )

    # Seed AI connection
    _setup_ai_connection(db_session, test_user.id)

    # Mock authorization
    mock_auth_result = MagicMock()
    mock_auth_result.authorized = True
    mock_auth_result.owner = test_user

    # Mock AI provider
    mock_response = BotResponseResult(answer_text="Here is the explanation.", confidence=0.9)
    mock_provider = MagicMock()
    mock_provider.generate_bot_response.return_value = mock_response
    mock_provider_cls = MagicMock(return_value=mock_provider)

    ctx, client = _mock_github_client(post_comment_id=12345)

    with patch("app.bot.bot_orchestration_service.authorize_mention", new_callable=AsyncMock, return_value=mock_auth_result), \
         patch("app.bot.bot_orchestration_service.GitHubAppClient", return_value=ctx), \
         patch("app.bot.bot_orchestration_service.get_provider", return_value=mock_provider_cls), \
         patch("app.bot.bot_orchestration_service.ai_connection_service.get_decrypted_api_key", return_value="fake-api-key-for-test"), \
         patch("app.bot.bot_orchestration_service.build_bot_context", new_callable=AsyncMock, return_value=_fake_bot_context()):
        await handle_mention(db_session, event, test_user_repository, normalized)

    interaction = db_session.query(BotInteraction).filter_by(github_event_id=event.id).one()
    assert interaction.status == "completed"
    assert interaction.intent == "issue_explain"
    assert interaction.response_text == "Here is the explanation."
    assert interaction.github_reply_comment_id == 12345
    assert interaction.completed_at is not None

    # Verify AI was called
    mock_provider.generate_bot_response.assert_called_once()
    # Verify comment was posted
    client.post_issue_comment.assert_awaited_once()


@pytest.mark.asyncio
async def test_provider_failure_no_github_post(db_session, test_user_repository, test_user):
    """AI provider raises → BotInteraction(status=failed), no GitHub comment posted."""
    event = _make_event(db_session, "provider-fail-1")
    normalized = _make_normalized(
        delivery_id="provider-fail-1",
        comment_body="@repomedic explain this issue",
    )

    _setup_ai_connection(db_session, test_user.id)

    mock_auth_result = MagicMock()
    mock_auth_result.authorized = True
    mock_auth_result.owner = test_user

    mock_provider = MagicMock()
    mock_provider.generate_bot_response.side_effect = RuntimeError("API quota exceeded")
    mock_provider_cls = MagicMock(return_value=mock_provider)

    ctx, client = _mock_github_client()

    with patch("app.bot.bot_orchestration_service.authorize_mention", new_callable=AsyncMock, return_value=mock_auth_result), \
         patch("app.bot.bot_orchestration_service.GitHubAppClient", return_value=ctx), \
         patch("app.bot.bot_orchestration_service.get_provider", return_value=mock_provider_cls), \
         patch("app.bot.bot_orchestration_service.ai_connection_service.get_decrypted_api_key", return_value="fake-api-key-for-test"), \
         patch("app.bot.bot_orchestration_service.build_bot_context", new_callable=AsyncMock, return_value=_fake_bot_context()):
        await handle_mention(db_session, event, test_user_repository, normalized)

    interaction = db_session.query(BotInteraction).filter_by(github_event_id=event.id).one()
    assert interaction.status == "failed"
    assert "API quota exceeded" in interaction.error_message
    assert interaction.completed_at is not None

    # No GitHub comment posted
    client.post_issue_comment.assert_not_awaited()


@pytest.mark.asyncio
async def test_github_post_failure(db_session, test_user_repository, test_user):
    """Comment posting raises → BotInteraction(status=failed)."""
    event = _make_event(db_session, "post-fail-1")
    normalized = _make_normalized(
        delivery_id="post-fail-1",
        comment_body="@repomedic explain this issue",
    )

    _setup_ai_connection(db_session, test_user.id)

    mock_auth_result = MagicMock()
    mock_auth_result.authorized = True
    mock_auth_result.owner = test_user

    mock_response = BotResponseResult(answer_text="answer", confidence=0.8)
    mock_provider = MagicMock()
    mock_provider.generate_bot_response.return_value = mock_response
    mock_provider_cls = MagicMock(return_value=mock_provider)

    ctx, client = _mock_github_client()
    client.post_issue_comment = AsyncMock(side_effect=RuntimeError("GitHub 500"))

    with patch("app.bot.bot_orchestration_service.authorize_mention", new_callable=AsyncMock, return_value=mock_auth_result), \
         patch("app.bot.bot_orchestration_service.GitHubAppClient", return_value=ctx), \
         patch("app.bot.bot_orchestration_service.get_provider", return_value=mock_provider_cls), \
         patch("app.bot.bot_orchestration_service.ai_connection_service.get_decrypted_api_key", return_value="fake-api-key-for-test"), \
         patch("app.bot.bot_orchestration_service.build_bot_context", new_callable=AsyncMock, return_value=_fake_bot_context()):
        await handle_mention(db_session, event, test_user_repository, normalized)

    interaction = db_session.query(BotInteraction).filter_by(github_event_id=event.id).one()
    assert interaction.status == "failed"
    assert "GitHub 500" in interaction.error_message
    assert interaction.completed_at is not None


@pytest.mark.asyncio
async def test_api_key_not_logged(db_session, test_user_repository, test_user):
    """Verify decrypted API key never appears in BotInteraction columns."""
    event = _make_event(db_session, "key-check-1")
    normalized = _make_normalized(
        delivery_id="key-check-1",
        comment_body="@repomedic explain this issue",
    )

    _setup_ai_connection(db_session, test_user.id)

    mock_auth_result = MagicMock()
    mock_auth_result.authorized = True
    mock_auth_result.owner = test_user

    mock_response = BotResponseResult(answer_text="answer", confidence=0.9)
    mock_provider = MagicMock()
    mock_provider.generate_bot_response.return_value = mock_response
    mock_provider_cls = MagicMock(return_value=mock_provider)

    ctx, client = _mock_github_client(post_comment_id=55555)

    with patch("app.bot.bot_orchestration_service.authorize_mention", new_callable=AsyncMock, return_value=mock_auth_result), \
         patch("app.bot.bot_orchestration_service.GitHubAppClient", return_value=ctx), \
         patch("app.bot.bot_orchestration_service.get_provider", return_value=mock_provider_cls), \
         patch("app.bot.bot_orchestration_service.ai_connection_service.get_decrypted_api_key", return_value="fake-api-key-for-test"), \
         patch("app.bot.bot_orchestration_service.build_bot_context", new_callable=AsyncMock, return_value=_fake_bot_context()):
        await handle_mention(db_session, event, test_user_repository, normalized)

    interaction = db_session.query(BotInteraction).filter_by(github_event_id=event.id).one()

    # Verify key doesn't leak into any column
    for col_name in ("response_text", "error_message", "question_text", "skip_reason"):
        val = getattr(interaction, col_name)
        if val is not None:
            assert "fake-api-key-for-test" not in val, f"API key leaked in {col_name}"


@pytest.mark.asyncio
async def test_each_authorization_denial_creates_skipped_row(db_session, test_user_repository):
    """Each denial reason produces a skipped BotInteraction with the correct skip_reason."""
    denial_reasons = [
        "monitoring_disabled",
        "owner_unresolved",
        "ai_not_configured",
        "insufficient_permission",
        "permission_check_failed",
        "rate_limited",
    ]
    for i, reason in enumerate(denial_reasons):
        delivery_id = f"denial-{reason}-{i}"
        event = _make_event(db_session, delivery_id)
        normalized = _make_normalized(
            delivery_id=delivery_id,
            comment_body="@repomedic explain this issue",
        )

        mock_auth_result = MagicMock()
        mock_auth_result.authorized = False
        mock_auth_result.skip_reason = reason

        with patch("app.bot.bot_orchestration_service.authorize_mention", new_callable=AsyncMock, return_value=mock_auth_result):
            await handle_mention(db_session, event, test_user_repository, normalized)

        interaction = db_session.query(BotInteraction).filter_by(github_event_id=event.id).one()
        assert interaction.status == "skipped"
        assert interaction.skip_reason == reason
