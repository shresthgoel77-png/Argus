"""
Tests for the RCA engine, validator, and API endpoint.

AI-dependent tests skip cleanly when AI_API_KEY is unset.
"""

import datetime
import os
import time

import pytest
import requests

# Isolate test database BEFORE any app imports
os.environ["DETECTION_POLL_INTERVAL_SECONDS"] = "3600"
os.environ["DATABASE_URL"] = "sqlite:///./test_incidents_rca.db"
os.environ["PROMETHEUS_URL"] = "http://localhost:9090"
os.environ["LOKI_URL"] = "http://localhost:3100"

from fastapi.testclient import TestClient

from app.main import app
from app.db import Base, SessionLocal, engine
from app.models import Evidence, Incident
from app.ai.validator import RCAValidationError, validate_rca_output
from app.ai.schema import ALLOWED_REMEDIATION_TYPES
import app.ai.engine as rca_engine

SIMULATOR_URL = os.getenv("SIMULATOR_URL", "http://localhost:9000")
client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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


def _create_investigated_incident(db=None):
    """Helper: create an incident in 'investigated' status with evidence."""
    close_db = db is None
    if db is None:
        db = SessionLocal()

    incident = Incident(
        type="high_error_rate",
        service="simulator",
        severity="high",
        status="investigated",
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        initial_metrics={"error_rate": "15%"},
        trigger="cpu_usage_high",
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)

    ev1 = Evidence(
        incident_id=incident.id,
        category="observed_fact",
        content={"metric": "cpu", "value": 95, "source": "prometheus"},
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    ev2 = Evidence(
        incident_id=incident.id,
        category="hypothesis",
        content={"hypothesis": "bad deployment caused CPU spike"},
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add_all([ev1, ev2])
    db.commit()
    db.refresh(ev1)
    db.refresh(ev2)

    incident_id = incident.id
    ev_ids = [str(ev1.id), str(ev2.id)]

    if close_db:
        db.close()

    return incident_id, ev_ids


# ---------------------------------------------------------------------------
# 1. Status guard tests (no AI key needed)
# ---------------------------------------------------------------------------

def test_rca_returns_404_for_unknown_incident():
    """POST on unknown incident -> 404."""
    response = client.post("/ai/rca/999999")
    assert response.status_code == 404


def test_rca_returns_409_for_non_investigated_incident():
    """POST on an incident still in 'investigating' status -> 409."""
    db = SessionLocal()
    incident = Incident(
        type="high_error_rate",
        service="simulator",
        severity="high",
        status="investigating",
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    iid = incident.id
    db.close()

    response = client.post(f"/ai/rca/{iid}")
    assert response.status_code == 409
    assert "investigated" in response.json()["detail"].lower() or "status" in response.json()["detail"].lower()


def test_rca_returns_409_for_duplicate_rca():
    """Second POST on an already-rca_complete incident -> 409."""
    db = SessionLocal()
    incident = Incident(
        type="high_error_rate",
        service="simulator",
        severity="high",
        status="rca_complete",
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)

    # Also add an existing ai_rca evidence row
    rca_evidence = Evidence(
        incident_id=incident.id,
        category="ai_rca",
        content={"summary": "already done"},
    )
    db.add(rca_evidence)
    db.commit()
    iid = incident.id
    db.close()

    response = client.post(f"/ai/rca/{iid}")
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# 2. Validator unit tests (no AI key needed)
# ---------------------------------------------------------------------------

def test_validate_rca_output_rejects_hallucinated_evidence_id():
    """An evidence ID not in the package is rejected."""
    raw = {
        "summary": "test",
        "impact": "test",
        "affected_components": ["svc"],
        "root_cause": "test",
        "confidence": "low",
        "supporting_evidence": ["999"],  # hallucinated ID
        "alternative_hypotheses": [],
        "recommended_fix": "test",
        "recommended_remediation": {
            "action_type": "rollback_deployment",
            "params": {},
            "rationale": "test",
        },
    }
    evidence_package = {
        "evidence": [{"id": "1", "category": "observed_fact", "content": {}}]
    }
    with pytest.raises(RCAValidationError, match="hallucinated evidence id: 999"):
        validate_rca_output(raw, evidence_package)


def test_validate_rca_output_rejects_invalid_remediation_type():
    """An action_type not in the allowlist is rejected."""
    raw = {
        "summary": "test",
        "impact": "test",
        "affected_components": ["svc"],
        "root_cause": "test",
        "confidence": "low",
        "supporting_evidence": ["1"],
        "alternative_hypotheses": [],
        "recommended_fix": "test",
        "recommended_remediation": {
            "action_type": "delete_db",  # not allowed
            "params": {},
            "rationale": "test",
        },
    }
    evidence_package = {
        "evidence": [{"id": "1", "category": "observed_fact", "content": {}}]
    }
    with pytest.raises(RCAValidationError, match="Invalid remediation action_type"):
        validate_rca_output(raw, evidence_package)


def test_validate_rca_output_accepts_valid_response():
    """A fully valid response passes validation."""
    raw = {
        "summary": "test",
        "impact": "test",
        "affected_components": ["svc"],
        "root_cause": "bad deploy",
        "confidence": "high",
        "supporting_evidence": ["1", "2"],
        "alternative_hypotheses": ["misconfiguration"],
        "recommended_fix": "rollback",
        "recommended_remediation": {
            "action_type": "rollback_deployment",
            "params": {"version": "v1.2"},
            "rationale": "roll it back",
        },
    }
    evidence_package = {
        "evidence": [
            {"id": "1", "category": "observed_fact", "content": {}},
            {"id": "2", "category": "hypothesis", "content": {}},
        ]
    }
    result = validate_rca_output(raw, evidence_package)
    assert result.confidence == "high"
    assert result.recommended_remediation.action_type == "rollback_deployment"


# ---------------------------------------------------------------------------
# 3. Engine retry-then-fail with monkeypatched hallucination (no AI key)
# ---------------------------------------------------------------------------

def test_rca_engine_retry_then_fail_on_hallucinated_response(monkeypatch):
    """
    Inject a response with a hallucinated evidence ID. Confirm:
    - validate_rca_output raises RCAValidationError
    - run_rca's retry-then-fail path persists ai_rca_error rows
    - endpoint returns 502
    """
    incident_id, real_ev_ids = _create_investigated_incident()

    hallucinated_response = {
        "summary": "test summary",
        "impact": "high impact",
        "affected_components": ["svc"],
        "root_cause": "bad deploy",
        "confidence": "high",
        "supporting_evidence": ["FAKE_ID_999"],  # hallucinated
        "alternative_hypotheses": [],
        "recommended_fix": "rollback",
        "recommended_remediation": {
            "action_type": "rollback_deployment",
            "params": {},
            "rationale": "roll it back",
        },
    }

    call_count = {"n": 0}

    def mock_call_rca_model(evidence_package):
        call_count["n"] += 1
        return hallucinated_response

    # Also mock the retry path
    def mock_call_retry(evidence_package, retry_prompt):
        call_count["n"] += 1
        return hallucinated_response  # Still hallucinated on retry

    monkeypatch.setattr(rca_engine, "call_rca_model", mock_call_rca_model)
    monkeypatch.setattr(rca_engine, "_call_retry", mock_call_retry)

    response = client.post(f"/ai/rca/{incident_id}")
    assert response.status_code == 502
    assert "validation failed" in response.json()["detail"].lower() or "hallucinated" in response.json()["detail"].lower()

    # Verify ai_rca_error rows were persisted
    db = SessionLocal()
    error_rows = (
        db.query(Evidence)
        .filter(Evidence.incident_id == incident_id, Evidence.category == "ai_rca_error")
        .all()
    )
    assert len(error_rows) >= 2, f"Expected at least 2 error rows, got {len(error_rows)}"

    # Verify NO ai_rca success row
    success_rows = (
        db.query(Evidence)
        .filter(Evidence.incident_id == incident_id, Evidence.category == "ai_rca")
        .all()
    )
    assert len(success_rows) == 0

    # Verify incident status unchanged
    incident = db.get(Incident, incident_id)
    assert incident.status == "investigated"
    db.close()


# ---------------------------------------------------------------------------
# 4. Full happy path (requires AI_API_KEY)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="requires valid GEMINI_API_KEY",
)
def test_rca_happy_path_real_ai():
    """
    Full happy path: investigated incident -> RCA succeeds via real AI,
    evidence row persisted with category='ai_rca', incident status
    becomes 'rca_complete', action_type is allowlisted.
    """
    incident_id, ev_ids = _create_investigated_incident()

    response = client.post(f"/ai/rca/{incident_id}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    body = response.json()

    assert body["incident_id"] == incident_id
    assert "rca" in body
    assert "evidence_id" in body

    rca = body["rca"]
    assert rca["confidence"] in ("low", "medium", "high")
    assert rca["recommended_remediation"]["action_type"] in ALLOWED_REMEDIATION_TYPES

    # Verify all supporting_evidence IDs are real
    for eid in rca["supporting_evidence"]:
        assert str(eid) in ev_ids, f"Evidence ID {eid} not in real evidence {ev_ids}"

    # Verify DB state
    db = SessionLocal()
    incident = db.get(Incident, incident_id)
    assert incident.status == "rca_complete"

    rca_evidence = (
        db.query(Evidence)
        .filter(Evidence.incident_id == incident_id, Evidence.category == "ai_rca")
        .first()
    )
    assert rca_evidence is not None
    assert rca_evidence.id == body["evidence_id"]
    db.close()

    # Second POST should 409
    response2 = client.post(f"/ai/rca/{incident_id}")
    assert response2.status_code == 409
