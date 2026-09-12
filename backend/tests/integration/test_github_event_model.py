import pytest
from sqlalchemy.exc import IntegrityError
from app.models.github_event import GitHubEvent
import uuid

def test_create_github_event_required_fields_only(db_session):
    event = GitHubEvent(
        delivery_id=f"del_{uuid.uuid4()}",
        event_type="issue",
        payload={"key": "value"}
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    assert event.id is not None
    assert event.delivery_id.startswith("del_")
    assert event.event_type == "issue"
    assert event.payload == {"key": "value"}
    assert event.status == "received"
    assert event.repository_id is None
    assert event.received_at is not None
    assert event.processed_at is None

def test_github_event_delivery_id_unique(db_session):
    del_id = f"del_{uuid.uuid4()}"
    event1 = GitHubEvent(
        delivery_id=del_id,
        event_type="push",
        payload={}
    )
    db_session.add(event1)
    db_session.commit()

    event2 = GitHubEvent(
        delivery_id=del_id,
        event_type="pull_request",
        payload={}
    )
    db_session.add(event2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
