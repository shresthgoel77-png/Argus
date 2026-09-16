import pytest
import uuid
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text, inspect, select, func
from app.models.bot_interaction import BotInteraction
from app.models.repository import Repository
from app.models.github_event import GitHubEvent
from app.models.user import User
from app.models.github_connection import GitHubConnection

def test_create_bot_interaction(db_session):
    user = User(email="test@example.com", auth_provider="github")
    db_session.add(user)
    db_session.flush()

    conn = GitHubConnection(user_id=user.id, installation_id=111, account_login="octocat", account_type="User")
    db_session.add(conn)
    db_session.flush()

    repo = Repository(
        connection_id=conn.id,
        github_repo_id=123,
        full_name="test/test-repo",
        private=False
    )
    db_session.add(repo)
    db_session.flush()

    event = GitHubEvent(
        delivery_id="delivery-123",
        event_type="issue_comment",
        action="created",
        payload={"issue": {"number": 1}}
    )
    db_session.add(event)
    db_session.flush()

    interaction = BotInteraction(
        repository_id=repo.id,
        github_event_id=event.id,
        requester_github_login="octocat",
        intent="pr_summary",
        question_text="Please summarize this PR"
    )
    db_session.add(interaction)
    db_session.commit()

    assert interaction.id is not None
    assert interaction.status == "pending"
    assert interaction.intent == "pr_summary"
    assert interaction.created_at is not None

def test_bot_interaction_fks(db_session):
    try:
        db_session.execute(text("PRAGMA foreign_keys = ON"))
    except Exception:
        pass

    i1 = BotInteraction(
        repository_id=uuid.uuid4(),
        github_event_id=uuid.uuid4(),
        requester_github_login="octocat",
        intent="ci_status",
        question_text="fk fail test"
    )
    db_session.add(i1)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

def test_bot_interaction_unique_github_event_id(db_session):
    user = User(email="test2@example.com", auth_provider="github")
    db_session.add(user)
    db_session.flush()

    conn = GitHubConnection(user_id=user.id, installation_id=222, account_login="octocat2", account_type="User")
    db_session.add(conn)
    db_session.flush()

    repo = Repository(
        connection_id=conn.id,
        github_repo_id=124, 
        full_name="test/test", 
        private=False
    )
    db_session.add(repo)
    db_session.flush()

    event = GitHubEvent(delivery_id="deliv-222", event_type="issue_comment", payload={})
    db_session.add(event)
    db_session.flush()

    i1 = BotInteraction(
        repository_id=repo.id,
        github_event_id=event.id,
        requester_github_login="octocat",
        intent="repo_attention",
        question_text="hello"
    )
    db_session.add(i1)
    db_session.commit()

    i2 = BotInteraction(
        repository_id=repo.id,
        github_event_id=event.id,
        requester_github_login="octocat",
        intent="repo_attention",
        question_text="duplicate attempt"
    )
    db_session.add(i2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

def test_bot_interaction_invalid_intent_rejected(db_session):
    user = User(email="test3@example.com", auth_provider="github")
    db_session.add(user)
    db_session.flush()

    conn = GitHubConnection(user_id=user.id, installation_id=333, account_login="octocat", account_type="User")
    db_session.add(conn)
    db_session.flush()
    repo = Repository(connection_id=conn.id, github_repo_id=333, full_name="test/test-repo3", private=False)
    db_session.add(repo)
    db_session.flush()
    event = GitHubEvent(delivery_id="deliv-333", event_type="issue_comment", payload={})
    db_session.add(event)
    db_session.flush()

    interaction = BotInteraction(
        repository_id=repo.id,
        github_event_id=event.id,
        requester_github_login="octocat",
        intent="invalid_fake_intent",
        question_text="hello"
    )
    db_session.add(interaction)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

def test_bot_interaction_composite_index(db_session):
    inspector = inspect(db_session.bind)
    indexes = inspector.get_indexes("bot_interactions")
    found_composite = False
    for idx in indexes:
        if idx["name"] == "ix_bot_interactions_repo_created_desc":
            found_composite = True
    assert found_composite, "Composite index (repository_id, created_at DESC) not found in db metadata"

def test_bot_interaction_count_query(db_session):
    user = User(email="test4@example.com", auth_provider="github")
    db_session.add(user)
    db_session.flush()

    conn = GitHubConnection(user_id=user.id, installation_id=444, account_login="octocat4", account_type="User")
    db_session.add(conn)
    db_session.flush()
    repo = Repository(connection_id=conn.id, github_repo_id=444, full_name="test/test-repo4", private=False)
    db_session.add(repo)
    db_session.flush()
    event = GitHubEvent(delivery_id="deliv-444", event_type="issue_comment", payload={})
    db_session.add(event)
    db_session.flush()

    interaction = BotInteraction(
        repository_id=repo.id,
        github_event_id=event.id,
        requester_github_login="octocat",
        intent="pr_summary",
        question_text="test query"
    )
    db_session.add(interaction)
    db_session.commit()

    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    
    stmt = (
        select(func.count(BotInteraction.id))
        .where(BotInteraction.repository_id == repo.id)
        .where(BotInteraction.created_at >= one_hour_ago)
    )
    
    result = db_session.execute(stmt).scalar()
    assert result == 1
