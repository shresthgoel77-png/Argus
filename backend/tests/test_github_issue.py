"""
Tests for the GitHub issue integration.
IMPORTANT: The actual HTTP call to api.github.com in `client.py` is mocked using `unittest.mock.patch("requests.post")`
for ALL tests in this file, regardless of whether real credentials happen to be present in the test environment.
These tests must NEVER create a real GitHub issue.
"""
import datetime
import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_github_issue.db"

from app.main import app
from app.db import Base, SessionLocal, engine
from app.models import Incident, Evidence
from app.github.client import get_github_status

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.query(Evidence).delete()
    db.query(Incident).delete()
    db.commit()
    db.close()
    yield
    db = SessionLocal()
    db.query(Evidence).delete()
    db.query(Incident).delete()
    db.commit()
    db.close()

def _create_incident(status="rca_complete", include_rca=True):
    db = SessionLocal()
    
    timestamp = datetime.datetime.now(datetime.timezone.utc)
    incident = Incident(
        type="bad_deployment",
        service="simulator",
        severity="high",
        status=status,
        timestamp=timestamp,
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    inc_id = incident.id
    
    if include_rca:
        ai_rca_ev = Evidence(
            incident_id=inc_id,
            category="ai_rca",
            content={
                "summary": "High error rate due to broken deployment.",
            }
        )
        db.add(ai_rca_ev)
        db.commit()
        
    db.close()
    return inc_id

def test_github_status_no_env(monkeypatch):
    # Test 1: get_github_status() with no env vars set -> configured=False.
    monkeypatch.setenv("GITHUB_TOKEN", "")
    monkeypatch.setenv("GITHUB_REPO", "")
    
    status = get_github_status()
    assert status["configured"] is False

def test_github_status_malformed_repo(monkeypatch):
    # Test 2: get_github_status() with a malformed GITHUB_REPO -> configured=False.
    monkeypatch.setenv("GITHUB_TOKEN", "fake_token")
    monkeypatch.setenv("GITHUB_REPO", "notarepo")  # Missing slash
    
    status = get_github_status()
    assert status["configured"] is False

@patch("requests.post")
def test_create_issue_happy_path(mock_post, monkeypatch):
    """
    Test 3: create_incident_issue on a real rca_complete incident, with the HTTP
    call mocked to return a successful 201, persists a real
    github_issue evidence row with the mocked issue_number/url and
    returns it; incident.status is unchanged by this call.
    """
    monkeypatch.setenv("GITHUB_TOKEN", "fake_token")
    monkeypatch.setenv("GITHUB_REPO", "owner/repo")
    
    mock_post.return_value = MagicMock(status_code=201, json=lambda: {"number": 123, "html_url": "https://github.com/owner/repo/issues/123"})
    
    inc_id = _create_incident(status="rca_complete", include_rca=True)
    
    response = client.post(f"/incidents/{inc_id}/github-issue")
    
    assert response.status_code == 200
    data = response.json()
    assert data["issue_number"] == 123
    assert data["issue_url"] == "https://github.com/owner/repo/issues/123"
    
    db = SessionLocal()
    # Verify evidence
    issue_ev = db.query(Evidence).filter(Evidence.incident_id == inc_id, Evidence.category == "github_issue").first()
    assert issue_ev is not None
    assert issue_ev.content["issue_number"] == 123
    
    # Incident status must be unchanged
    incident = db.query(Incident).filter(Incident.id == inc_id).first()
    assert incident.status == "rca_complete"
    db.close()
    
    assert mock_post.called

@patch("requests.post")
def test_create_issue_duplicate_409(mock_post, monkeypatch):
    """
    Test 4: Second call on the same incident -> 409, no duplicate evidence row,
    no second (mocked) API call made.
    """
    monkeypatch.setenv("GITHUB_TOKEN", "fake_token")
    monkeypatch.setenv("GITHUB_REPO", "owner/repo")
    
    mock_post.return_value = MagicMock(status_code=201, json=lambda: {"number": 123, "html_url": "https://github.com/owner/repo/issues/123"})
    inc_id = _create_incident(status="rca_complete", include_rca=True)
    
    # Simulate a prior successful call by inserting evidence
    db = SessionLocal()
    issue_ev = Evidence(
        incident_id=inc_id,
        category="github_issue",
        content={"issue_number": 99}
    )
    db.add(issue_ev)
    db.commit()
    db.close()
    
    response = client.post(f"/incidents/{inc_id}/github-issue")
    assert response.status_code == 409
    assert mock_post.called is False

@patch("requests.post")
def test_create_issue_no_rca_409(mock_post, monkeypatch):
    """
    Test 5: create_incident_issue on an incident with no ai_rca evidence -> 409.
    """
    monkeypatch.setenv("GITHUB_TOKEN", "fake_token")
    monkeypatch.setenv("GITHUB_REPO", "owner/repo")
    
    inc_id = _create_incident(status="investigated", include_rca=False)
    
    response = client.post(f"/incidents/{inc_id}/github-issue")
    assert response.status_code == 409
    assert mock_post.called is False
    
@patch("requests.post")
def test_create_issue_api_error_502(mock_post, monkeypatch):
    """
    Test 6: With the HTTP call mocked to return a 401, create_incident_issue
    raises GitHubAPIError, a github_issue_error evidence row is
    persisted, and incident.status remains whatever it was before the
    attempt.
    """
    monkeypatch.setenv("GITHUB_TOKEN", "fake_token")
    monkeypatch.setenv("GITHUB_REPO", "owner/repo")
    
    mock_post.return_value = MagicMock(status_code=401, json=lambda: {"message": "Bad credentials"})
    
    inc_id = _create_incident(status="rca_complete", include_rca=True)
    
    response = client.post(f"/incidents/{inc_id}/github-issue")
    
    assert response.status_code == 502
    
    db = SessionLocal()
    # Verify error evidence
    err_ev = db.query(Evidence).filter(Evidence.incident_id == inc_id, Evidence.category == "github_issue_error").first()
    assert err_ev is not None
    assert "status 401" in err_ev.content["error"]
    
    # Status unchanged
    incident = db.query(Incident).filter(Incident.id == inc_id).first()
    assert incident.status == "rca_complete"
    db.close()

@patch("requests.post")
def test_create_issue_unconfigured_501(mock_post, monkeypatch):
    """
    Test 7: With GITHUB_TOKEN unset, POST /incidents/{id}/github-issue returns
    501 without attempting any HTTP call (assert the mock was never
    invoked).
    """
    monkeypatch.setenv("GITHUB_TOKEN", "")
    monkeypatch.setenv("GITHUB_REPO", "owner/repo")
    
    inc_id = _create_incident(status="rca_complete", include_rca=True)
    
    response = client.post(f"/incidents/{inc_id}/github-issue")
    assert response.status_code == 501
    assert mock_post.called is False
