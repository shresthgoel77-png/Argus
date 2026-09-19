import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.bot_interaction import BotInteraction
from app.models.finding import Finding
from app.models.github_connection import GitHubConnection
from app.models.github_event import GitHubEvent
from app.models.repository import Repository
from app.models.repository_health_snapshot import RepositoryHealthSnapshot
from app.models.user import User
from app.services.activity_feed_service import get_activity_feed


def seed_activity(db_session, repository: Repository) -> list[uuid.UUID]:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    event = GitHubEvent(
        delivery_id=f"activity-{uuid.uuid4()}",
        event_type="push",
        action="created",
        repository_id=repository.id,
        payload={"large": "x" * 10000},
        received_at=base + timedelta(minutes=5),
    )
    finding = Finding(
        repository_id=repository.id,
        category="security",
        type="dependency",
        title="Outdated dependency",
        description="Update the dependency.",
        severity="high",
        source="test",
        evidence={},
        detected_at=base + timedelta(minutes=4),
        resolved_at=base + timedelta(minutes=2),
    )
    snapshot = RepositoryHealthSnapshot(
        repository_id=repository.id,
        overall_score=82,
        category_scores={},
        reasons=[],
        computed_at=base + timedelta(minutes=3),
    )
    db_session.add_all([event, finding, snapshot])
    db_session.flush()
    interaction = BotInteraction(
        repository_id=repository.id,
        github_event_id=event.id,
        requester_github_login="tester",
        intent="ci_status",
        question_text="Is CI passing?",
        status="completed",
        created_at=base + timedelta(minutes=1),
    )
    db_session.add(interaction)
    db_session.commit()
    return [event.id, finding.id, snapshot.id, interaction.id]


def test_activity_feed_merges_sources_and_paginates(db_session, test_user_repository):
    references = seed_activity(db_session, test_user_repository)

    first_page, before = get_activity_feed(db_session, test_user_repository.id, limit=3)
    second_page, next_before = get_activity_feed(
        db_session, test_user_repository.id, before=before, limit=3
    )

    assert [item.source.value for item in first_page] == [
        "github_event",
        "finding_detected",
        "health_changed",
    ]
    assert [item.source.value for item in second_page] == [
        "finding_resolved",
        "bot_interaction",
    ]
    assert {(item.source, item.reference_id) for item in first_page}.isdisjoint(
        (item.source, item.reference_id) for item in second_page
    )
    assert next_before is not None
    assert all(reference not in {item.reference_id for item in first_page} for reference in references[3:])


def test_activity_feed_empty_repository(db_session, test_user_repository):
    items, before = get_activity_feed(db_session, test_user_repository.id)

    assert items == []
    assert before is None


@pytest.mark.asyncio
async def test_activity_feed_api_paginates_without_payload_or_duplicates(
    db_session, authorized_client, test_user_repository
):
    seed_activity(db_session, test_user_repository)

    first = await authorized_client.get(
        f"/api/v1/repositories/{test_user_repository.id}/activity?limit=2"
    )
    assert first.status_code == 200
    first_data = first.json()
    assert len(first_data["items"]) == 2
    assert "large" not in first.text

    second = await authorized_client.get(
        f"/api/v1/repositories/{test_user_repository.id}/activity",
        params={"limit": 2, "before": first_data["next_before"]},
    )
    assert second.status_code == 200
    second_ids = {
        (item["source"], item["reference_id"]) for item in second.json()["items"]
    }
    first_ids = {
        (item["source"], item["reference_id"]) for item in first_data["items"]
    }
    assert first_ids.isdisjoint(second_ids)


@pytest.mark.asyncio
async def test_activity_feed_api_rejects_unowned_repository(
    db_session, authorized_client
):
    other_user = User(
        email=f"other-{uuid.uuid4()}@example.com",
        display_name="Other User",
        auth_provider="development",
        external_auth_id=str(uuid.uuid4()),
    )
    db_session.add(other_user)
    db_session.flush()
    connection = GitHubConnection(
        user_id=other_user.id,
        installation_id=uuid.uuid4().int >> 64,
        account_login="other-org",
        account_type="Organization",
        status="active",
    )
    db_session.add(connection)
    db_session.flush()
    repository = Repository(
        connection_id=connection.id,
        github_repo_id=uuid.uuid4().int >> 64,
        full_name="other-org/repo",
        default_branch="main",
        monitoring_enabled=True,
    )
    db_session.add(repository)
    db_session.commit()

    response = await authorized_client.get(
        f"/api/v1/repositories/{repository.id}/activity"
    )

    assert response.status_code == 404