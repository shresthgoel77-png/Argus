import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.models.bot_interaction import BotInteraction
from app.models.github_event import GitHubEvent
from app.models.github_connection import GitHubConnection
from app.models.repository import Repository
from app.models.user import User


def add_interaction(db_session, repository: Repository, *, index: int, status: str = "completed"):
    event = GitHubEvent(
        delivery_id=f"bot-activity-{uuid.uuid4()}",
        event_type="issue_comment",
        installation_id=123456,
        repository_github_id=repository.github_repo_id,
        repository_id=repository.id,
        payload={},
    )
    db_session.add(event)
    db_session.flush()
    interaction = BotInteraction(
        repository_id=repository.id,
        github_event_id=event.id,
        requester_github_login=f"requester-{index}",
        intent="ci_status",
        question_text="x" * 600,
        status=status,
        skip_reason="insufficient_permission" if status == "skipped" else None,
        response_text="A completed response" if status == "completed" else "should not be exposed",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=index),
    )
    db_session.add(interaction)
    db_session.commit()
    return interaction


@pytest.mark.asyncio
async def test_bot_interactions_are_owned_paginated_and_newest_first(
    db_session, authorized_client: AsyncClient, test_user_repository: Repository
):
    add_interaction(db_session, test_user_repository, index=1)
    add_interaction(db_session, test_user_repository, index=2, status="skipped")
    add_interaction(db_session, test_user_repository, index=3)

    response = await authorized_client.get(
        f"/api/v1/repositories/{test_user_repository.id}/bot-interactions?limit=2&offset=0"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert data["limit"] == 2
    assert data["offset"] == 0
    assert [item["requester_github_login"] for item in data["items"]] == [
        "requester-1",
        "requester-2",
    ]
    assert len(data["items"][0]["question_text"]) == 500
    assert data["items"][0]["response_text"] == "A completed response"
    assert data["items"][1]["skip_reason"] == "insufficient_permission"
    assert data["items"][1]["response_text"] is None

    next_page = await authorized_client.get(
        f"/api/v1/repositories/{test_user_repository.id}/bot-interactions?limit=2&offset=2"
    )
    assert [item["requester_github_login"] for item in next_page.json()["items"]] == [
        "requester-3"
    ]


@pytest.mark.asyncio
async def test_bot_interactions_returns_404_for_unowned_repository(
    db_session, authorized_client: AsyncClient
):
    other_user = User(
        email=f"other-{uuid.uuid4()}@example.com",
        display_name="Other User",
        auth_provider="development",
        external_auth_id=str(uuid.uuid4()),
    )
    db_session.add(other_user)
    db_session.flush()
    other_connection = GitHubConnection(
        user_id=other_user.id,
        installation_id=654321,
        account_login="other-org",
        account_type="Organization",
        status="active",
    )
    db_session.add(other_connection)
    db_session.flush()
    other_repository = Repository(
        connection_id=other_connection.id,
        github_repo_id=54321,
        full_name="other-org/other-repo",
        default_branch="main",
        monitoring_enabled=True,
    )
    db_session.add(other_repository)
    db_session.commit()

    response = await authorized_client.get(
        f"/api/v1/repositories/{other_repository.id}/bot-interactions"
    )

    assert response.status_code == 404