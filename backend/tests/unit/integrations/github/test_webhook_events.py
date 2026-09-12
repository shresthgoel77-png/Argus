import pytest

from app.integrations.github.webhook_events import (
    NormalizedWebhookEvent,
    RepoRef,
    parse_webhook_payload,
)


def test_parse_pull_request():
    payload = {
        "action": "opened",
        "installation": {"id": 123},
        "repository": {"id": 100, "full_name": "octocat/hello-world"},
    }
    event = parse_webhook_payload("pull_request", "delivery-123", payload)
    
    assert event.event_type == "pull_request"
    assert event.delivery_id == "delivery-123"
    assert event.action == "opened"
    assert event.installation_id == 123
    assert event.repository == RepoRef(100, "octocat/hello-world")
    assert event.installation_account_login is None
    assert event.installation_account_type is None
    assert event.repositories_removed == []


def test_parse_issues():
    payload = {
        "action": "closed",
        "installation": {"id": 124},
        "repository": {"id": 200, "full_name": "user/repo"},
    }
    event = parse_webhook_payload("issues", "delivery-124", payload)
    assert event.event_type == "issues"
    assert event.repository == RepoRef(200, "user/repo")
    assert event.action == "closed"


def test_parse_issue_comment():
    payload = {
        "action": "created",
        "repository": {"id": 300, "full_name": "user/repo3"},
    }
    event = parse_webhook_payload("issue_comment", "delivery-125", payload)
    assert event.event_type == "issue_comment"
    assert event.repository == RepoRef(300, "user/repo3")
    assert event.installation_id is None


def test_parse_workflow_run():
    payload = {
        "action": "completed",
        "repository": {"id": 400, "full_name": "a/b"},
    }
    event = parse_webhook_payload("workflow_run", "delivery-126", payload)
    assert event.event_type == "workflow_run"
    assert event.repository == RepoRef(400, "a/b")


def test_parse_push():
    # push typically doesn't have an action field in the same way (can be None)
    payload = {
        "repository": {"id": 500, "full_name": "org/proj"},
    }
    event = parse_webhook_payload("push", "delivery-127", payload)
    assert event.event_type == "push"
    assert event.repository == RepoRef(500, "org/proj")
    assert event.action is None


def test_parse_installation():
    payload = {
        "action": "created",
        "installation": {
            "id": 999,
            "account": {"login": "my-org", "type": "Organization"},
        },
    }
    event = parse_webhook_payload("installation", "delivery-128", payload)
    assert event.event_type == "installation"
    assert event.repository is None
    assert event.installation_id == 999
    assert event.installation_account_login == "my-org"
    assert event.installation_account_type == "Organization"


def test_parse_installation_repositories():
    payload = {
        "action": "removed",
        "installation": {"id": 888},
        "repositories_removed": [
            {"id": 1, "full_name": "gone/repo1"},
            {"id": 2, "full_name": "gone/repo2"},
        ],
    }
    event = parse_webhook_payload("installation_repositories", "delivery-129", payload)
    assert event.event_type == "installation_repositories"
    assert event.repository is None
    assert len(event.repositories_removed) == 2
    assert event.repositories_removed[0] == RepoRef(1, "gone/repo1")
    assert event.repositories_removed[1] == RepoRef(2, "gone/repo2")


def test_parse_malformed_non_dict_payload():
    # If the payload isn't even a dict, should gracefully handle without exception
    payload = "not a dict" # type: ignore
    event = parse_webhook_payload("pull_request", "delivery-130", payload)
    assert event.action is None
    assert event.repository is None
    assert event.installation_id is None
    assert event.repositories_removed == []


def test_parse_partially_malformed_repository():
    payload = {
        "action": "opened",
        "repository": {"id": 100}, # missing full_name
        "repositories_removed": [
            {"full_name": "only-name"}, # missing id
            {"id": 12, "full_name": "valid/repo"}
        ]
    }
    event = parse_webhook_payload("installation_repositories", "delivery-131", payload)
    assert event.repository is None # Because full_name was missing
    assert len(event.repositories_removed) == 1
    assert event.repositories_removed[0] == RepoRef(12, "valid/repo")


def test_parse_malformed_installation():
    payload = {
        "installation": "not a dict",
        "repository": "not a dict",
        "repositories_removed": "not a list",
    }
    event = parse_webhook_payload("push", "delivery-132", payload)
    assert event.installation_id is None
    assert event.installation_account_login is None
    assert event.repository is None
    assert event.repositories_removed == []


def test_parse_unsupported_event_with_valid_shapes():
    payload = {
        "action": "completed",
        "installation": {
            "id": 999,
            "account": {"login": "my-org", "type": "Organization"},
        },
        "repository": {"id": 100, "full_name": "octocat/hello-world"},
        "repositories_removed": [
            {"id": 1, "full_name": "gone/repo1"}
        ]
    }
    event = parse_webhook_payload("some_random_event", "deliv", payload)
    
    assert event.event_type == "some_random_event"
    assert event.action == "completed"
    assert event.installation_id == 999
    
    # Should all be None/empty since this event type doesn't support them canonically:
    assert event.installation_account_login is None
    assert event.installation_account_type is None
    assert event.repository is None
    assert event.repositories_removed == []
    assert event.raw_payload == payload


