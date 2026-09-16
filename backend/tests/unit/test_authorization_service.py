from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.bot.authorization_service import authorize_mention
from app.models.bot_interaction import BotInteraction
from app.models.github_event import GitHubEvent


def _valid_status():
    return {"provider": "openai", "model": "test", "status": "valid"}


@pytest.fixture
def authorized_repository(test_user_repository, db_session):
    test_user_repository.monitoring_enabled = True
    db_session.commit()
    return test_user_repository


def _client(permission="write"):
    client = MagicMock()
    client.get_collaborator_permission = AsyncMock(return_value=permission)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=client)
    context.__aexit__ = AsyncMock(return_value=None)
    return context, client


@pytest.mark.asyncio
async def test_monitoring_disabled_short_circuits(test_user_repository):
    test_user_repository.monitoring_enabled = False
    result = await authorize_mention(test_user_repository, "commenter")
    assert not result.authorized
    assert result.skip_reason == "monitoring_disabled"


@pytest.mark.asyncio
async def test_owner_unresolved_short_circuits(authorized_repository):
    authorized_repository.connection.user = None
    result = await authorize_mention(authorized_repository, "commenter")
    assert result.skip_reason == "owner_unresolved"


@pytest.mark.asyncio
async def test_ai_not_configured_short_circuits(authorized_repository):
    context, _ = _client()
    with patch("app.bot.authorization_service.ai_connection_service.get_connection_status", return_value=None), \
            patch("app.bot.authorization_service.GitHubAppClient", return_value=context):
        result = await authorize_mention(authorized_repository, "commenter")
    assert result.skip_reason == "ai_not_configured"


@pytest.mark.asyncio
async def test_insufficient_permission(authorized_repository):
    context, _ = _client("read")
    with patch("app.bot.authorization_service.ai_connection_service.get_connection_status", return_value=_valid_status()), \
            patch("app.bot.authorization_service.GitHubAppClient", return_value=context):
        result = await authorize_mention(authorized_repository, "commenter")
    assert result.skip_reason == "insufficient_permission"


@pytest.mark.asyncio
async def test_permission_check_failure_denies(authorized_repository):
    context, client = _client()
    client.get_collaborator_permission.side_effect = RuntimeError("network")
    with patch("app.bot.authorization_service.ai_connection_service.get_connection_status", return_value=_valid_status()), \
            patch("app.bot.authorization_service.GitHubAppClient", return_value=context):
        result = await authorize_mention(authorized_repository, "commenter")
    assert result.skip_reason == "permission_check_failed"


@pytest.mark.asyncio
async def test_rate_limit_counts_only_trailing_hour(authorized_repository, db_session):
    event = GitHubEvent(delivery_id="old-event", event_type="issue_comment", payload={})
    db_session.add(event)
    db_session.flush()
    old = BotInteraction(
        repository_id=authorized_repository.id,
        github_event_id=event.id,
        requester_github_login="commenter",
        intent="pr_summary",
        question_text="old",
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    db_session.add(old)
    db_session.commit()

    context, _ = _client()
    with patch("app.bot.authorization_service.ai_connection_service.get_connection_status", return_value=_valid_status()), \
            patch("app.bot.authorization_service.GitHubAppClient", return_value=context), \
            patch("app.bot.authorization_service.settings.bot_max_interactions_per_hour", 1):
        result = await authorize_mention(authorized_repository, "commenter")
    assert result.authorized


@pytest.mark.asyncio
async def test_rate_limit_denies_trailing_hour_interaction(authorized_repository, db_session):
    event = GitHubEvent(delivery_id="recent-event", event_type="issue_comment", payload={})
    db_session.add(event)
    db_session.flush()
    interaction = BotInteraction(
        repository_id=authorized_repository.id,
        github_event_id=event.id,
        requester_github_login="commenter",
        intent="pr_summary",
        question_text="recent",
    )
    db_session.add(interaction)
    db_session.commit()

    context, _ = _client()
    with patch("app.bot.authorization_service.ai_connection_service.get_connection_status", return_value=_valid_status()), \
            patch("app.bot.authorization_service.GitHubAppClient", return_value=context), \
            patch("app.bot.authorization_service.settings.bot_max_interactions_per_hour", 1):
        result = await authorize_mention(authorized_repository, "commenter")
    assert result.skip_reason == "rate_limited"


@pytest.mark.asyncio
async def test_authorizes_write_permission(authorized_repository):
    context, client = _client("maintain")
    with patch("app.bot.authorization_service.ai_connection_service.get_connection_status", return_value=_valid_status()), \
            patch("app.bot.authorization_service.GitHubAppClient", return_value=context):
        result = await authorize_mention(authorized_repository, "commenter")
    assert result.authorized
    assert result.owner is authorized_repository.connection.user
    client.get_collaborator_permission.assert_awaited_once_with(
        authorized_repository.full_name, "commenter"
    )