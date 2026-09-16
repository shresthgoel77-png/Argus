import pytest
from sqlalchemy.exc import IntegrityError
from app.models.bot_interaction import BotInteraction
from app.models.repository import Repository
from app.models.github_event import GitHubEvent
from app.models.user import User
from app.models.github_connection import GitHubConnection

def test_create_bot_interaction(db_session):
    # Setup dependencies
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

    # Create BotInteraction
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

def test_bot_interaction_unique_github_event_id(db_session):
    # Setup dependencies
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

