"""
Tests for the verification API endpoint.

These tests verify:
- 404 behavior when incident doesn't exist
- 409 behavior when incident is not in "remediated" status
- 409 behavior when verification already exists
- Happy path: GET /incidents/{id}/verification returns null before verification
- Happy path: POST /verification/run/{id} completes and returns result
- Happy path: GET /incidents/{id}/verification returns the result after POST
- Real traffic generation during verification (per Prompt 1 pattern)
- Correct incident status transition to "resolved" or "remediation_failed"
"""

import datetime
import os
import time
import httpx
import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_verification_route.db"
os.environ["SIMULATOR_URL"] = "http://localhost:9000"
os.environ["PROMETHEUS_URL"] = "http://localhost:9090"
os.environ["VERIFICATION_MAX_WAIT_SECONDS"] = "60"
os.environ["VERIFICATION_POLL_INTERVAL_SECONDS"] = "2"
os.environ["DETECTION_WINDOW"] = "15s"
os.environ["ERROR_RATE_MEDIUM"] = "0.05"

from app.main import app
from app.db import Base, SessionLocal, engine
from app.models import Incident, VerificationResult, RemediationAction
from app.detection.engine import run_detection_pass
from app.remediation.handlers import handle_rollback_deployment

client = TestClient(app)


@pytest.fixture(autouse=True)
def db_session_fixture():
    """Set up and tear down test database."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    session.query(VerificationResult).delete()
    session.query(RemediationAction).delete()
    session.query(Incident).delete()
    session.commit()
    yield
    session = SessionLocal()
    session.query(VerificationResult).delete()
    session.query(RemediationAction).delete()
    session.query(Incident).delete()
    session.commit()


def generate_traffic(seconds: float):
    """Generates traffic to build real Prometheus state."""
    end_time = time.time() + seconds
    while time.time() < end_time:
        try:
            httpx.get(f"{os.environ['SIMULATOR_URL']}/api/checkout", timeout=1.0)
            httpx.post(f"{os.environ['SIMULATOR_URL']}/webhook/payment-event", json={}, timeout=1.0)
        except Exception:
            pass
        time.sleep(0.5)


def test_get_verification_returns_404_for_unknown_incident():
    """GET /incidents/{id}/verification should return 404 if incident doesn't exist."""
    response = client.get("/incidents/999/verification")
    assert response.status_code == 404
    assert "Incident not found" in response.json()["detail"]


def test_run_verification_returns_404_for_unknown_incident():
    """POST /verification/run/{id} should return 404 if incident doesn't exist."""
    response = client.post("/verification/run/999")
    assert response.status_code == 404
    assert "Incident not found" in response.json()["detail"]


def test_run_verification_returns_409_if_not_remediated():
    """POST /verification/run/{id} should return 409 if incident.status != 'remediated'."""
    db = SessionLocal()
    for status in ["open", "investigating", "investigated", "rca_complete", 
                   "remediation_proposed", "remediating", "execution_failed", "remediation_rejected"]:
        incident = Incident(
            type="high_error_rate",
            service="simulator",
            severity="high",
            status=status,
            timestamp=datetime.datetime.now(datetime.UTC),
            trigger="test",
            initial_metrics={"value": 10.0, "firing": True}
        )
        db.add(incident)
        db.commit()
        db.refresh(incident)
        inc_id = incident.id
        db.close()
        
        response = client.post(f"/verification/run/{inc_id}")
        assert response.status_code == 409
        assert "remediated" in response.json()["detail"].lower()
        
        db = SessionLocal()
        db.query(Incident).filter(Incident.id == inc_id).delete()
        db.commit()


def test_run_verification_returns_409_if_already_verified():
    """POST /verification/run/{id} should return 409 if verification result already exists."""
    db = SessionLocal()
    incident = Incident(
        type="high_error_rate",
        service="simulator",
        severity="high",
        status="remediated",
        timestamp=datetime.datetime.now(datetime.UTC),
        trigger="test",
        initial_metrics={"value": 10.0, "firing": True}
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    
    # Create an existing verification result
    existing_result = VerificationResult(
        incident_id=incident.id,
        before_metrics={"value": 10.0, "firing": True},
        after_metrics={"final_detector_result": {"firing": False}, "final_health_status": "healthy"},
        recovered=True,
        checked_at=datetime.datetime.now(datetime.UTC)
    )
    db.add(existing_result)
    db.commit()
    inc_id = incident.id
    db.close()
    
    # Try to run verification again
    response = client.post(f"/verification/run/{inc_id}")
    assert response.status_code == 409
    assert "already been performed" in response.json()["detail"].lower()


def test_get_verification_returns_null_before_running():
    """GET /incidents/{id}/verification should return null if no verification has run."""
    db = SessionLocal()
    incident = Incident(
        type="high_error_rate",
        service="simulator",
        severity="high",
        status="remediated",
        timestamp=datetime.datetime.now(datetime.UTC),
        trigger="test",
        initial_metrics={"value": 10.0, "firing": True}
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    inc_id = incident.id
    db.close()
    
    response = client.get(f"/incidents/{inc_id}/verification")
    assert response.status_code == 200
    assert response.json() is None


def test_happy_path_run_verification_with_real_recovery():
    """
    Full happy-path test:
    1. Trigger bad deployment
    2. Generate traffic so detector fires
    3. Run detection to get real incident
    4. Simulate RCA/remediation approval
    5. Execute rollback
    6. Run verification
    7. Confirm recovered=True, incident.status="resolved"
    """
    # 1. Reset and trigger bad deployment
    httpx.post(f"{os.environ['SIMULATOR_URL']}/simulate/reset", timeout=5.0)
    httpx.post(f"{os.environ['SIMULATOR_URL']}/simulate/bad-deployment", timeout=5.0)
    
    # 2. Generate traffic so Prometheus detects the incident
    generate_traffic(15.0)
    
    # 3. Run detection to capture real incident with real initial_metrics
    session = SessionLocal()
    detection_results = run_detection_pass(session, "simulator")
    
    assert len(detection_results) > 0, "Expected detection to find an incident"
    incident = detection_results[0]
    inc_id = incident.id
    assert incident.initial_metrics.get("firing") is True
    assert incident.initial_metrics.get("value", 0.0) > 0.0
    session.close()
    
    # 4. Simulate remediation flow (propose, approve, execute)
    session = SessionLocal()
    incident = session.query(Incident).filter(Incident.id == inc_id).first()
    incident.status = "remediating"
    session.commit()
    
    action = RemediationAction(
        incident_id=inc_id,
        action_type="rollback_deployment",
        params={},
        risk_level="medium",
        approved=True,
        approved_by="test_user",
        status="approved"
    )
    session.add(action)
    session.commit()
    
    # 5. Execute remediation handler
    result = handle_rollback_deployment(action)
    assert result["success"] is True
    
    incident.status = "remediated"
    session.commit()
    session.close()
    
    # 6. Start generating good traffic in background while verification runs
    import threading
    traffic_thread = threading.Thread(target=generate_traffic, args=(50.0,))
    traffic_thread.start()
    
    # Give Prometheus time to scrape
    time.sleep(1.0)
    
    # 7. Run verification endpoint
    response = client.post(f"/verification/run/{inc_id}")
    traffic_thread.join()
    
    assert response.status_code == 200, response.text
    data = response.json()
    
    # Verify response structure
    assert "verification_id" in data
    assert data["incident_id"] == inc_id
    assert "recovered" in data
    assert "before_metrics" in data
    assert "after_metrics" in data
    
    # Verify recovery result
    assert data["recovered"] is True, "Incident should be detected as recovered after rollback"
    assert data["before_metrics"]["firing"] is True
    assert data["before_metrics"]["value"] > 0.0
    assert "final_detector_result" in data["after_metrics"]
    assert data["after_metrics"]["final_detector_result"]["firing"] is False
    
    # 8. Verify incident status changed
    session = SessionLocal()
    incident = session.query(Incident).filter(Incident.id == inc_id).first()
    assert incident.status == "resolved"
    session.close()


def test_happy_path_get_verification_after_run():
    """GET /incidents/{id}/verification should return the result after POST completes."""
    # First create a verified incident (use minimal setup)
    db = SessionLocal()
    incident = Incident(
        type="high_error_rate",
        service="simulator",
        severity="high",
        status="resolved",
        timestamp=datetime.datetime.now(datetime.UTC),
        trigger="test",
        initial_metrics={"value": 10.0, "firing": True}
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    
    verification = VerificationResult(
        incident_id=incident.id,
        before_metrics={"value": 10.0, "firing": True},
        after_metrics={
            "final_detector_result": {"firing": False, "value": 0.0},
            "final_health_status": "healthy",
            "poll_history": []
        },
        recovered=True,
        checked_at=datetime.datetime.now(datetime.UTC)
    )
    db.add(verification)
    db.commit()
    db.refresh(verification)
    inc_id = incident.id
    ver_id = verification.id
    db.close()
    
    # Now fetch it via GET
    response = client.get(f"/incidents/{inc_id}/verification")
    assert response.status_code == 200
    data = response.json()
    assert data is not None
    assert data["id"] == ver_id
    assert data["incident_id"] == inc_id
    assert data["recovered"] is True
    assert data["before_metrics"]["firing"] is True
    assert data["after_metrics"]["final_detector_result"]["firing"] is False


def test_run_verification_non_recovery():
    """
    Test case where verification confirms NON-recovery:
    - Bad deployment active
    - Incident marked as remediated
    - But detector still firing after wait window
    - Should result in recovered=False, incident.status="remediation_failed"
    
    (This may be hard to trigger in live env, so uses real flow with short timeout)
    """
    # Reset to clean state
    httpx.post(f"{os.environ['SIMULATOR_URL']}/simulate/reset", timeout=5.0)
    
    # Trigger bad deployment
    httpx.post(f"{os.environ['SIMULATOR_URL']}/simulate/bad-deployment", timeout=5.0)
    
    # Generate traffic so detector fires
    generate_traffic(15.0)
    
    # Detect the incident
    session = SessionLocal()
    detection_results = run_detection_pass(session, "simulator")
    assert len(detection_results) > 0
    incident = detection_results[0]
    inc_id = incident.id
    session.close()
    
    # Mark as remediated WITHOUT actually executing rollback (simulator stays bad)
    session = SessionLocal()
    incident = session.query(Incident).filter(Incident.id == inc_id).first()
    incident.status = "remediated"
    session.commit()
    session.close()
    
    # Generate more traffic while verification runs (incident still bad)
    import threading
    traffic_thread = threading.Thread(target=generate_traffic, args=(35.0,))
    traffic_thread.start()
    time.sleep(1.0)
    
    # Run verification (should detect that it's still firing)
    response = client.post(f"/verification/run/{inc_id}")
    traffic_thread.join()
    
    assert response.status_code == 200, response.text
    data = response.json()
    
    # Should show NOT recovered
    assert data["recovered"] is False, "Should detect that bad deployment is still active"
    
    # Incident status should change to remediation_failed
    session = SessionLocal()
    incident = session.query(Incident).filter(Incident.id == inc_id).first()
    assert incident.status == "remediation_failed"
    session.close()


def test_double_click_protection():
    """
    Test that double-clicking "Run Verification" results in:
    - First click: 200 (or blocks and returns result when server is fast)
    - Second click: 409 once first completes and creates the row
    
    This is a client-side concern (button disabled during load),
    but server should also reject with 409.
    """
    db = SessionLocal()
    incident = Incident(
        type="high_error_rate",
        service="simulator",
        severity="high",
        status="remediated",
        timestamp=datetime.datetime.now(datetime.UTC),
        trigger="test",
        initial_metrics={"value": 10.0, "firing": True}
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    inc_id = incident.id
    db.close()
    
    # Create a verification result to simulate what happens after first call
    db = SessionLocal()
    incident = db.query(Incident).filter(Incident.id == inc_id).first()
    verification = VerificationResult(
        incident_id=inc_id,
        before_metrics={"value": 10.0, "firing": True},
        after_metrics={"final_detector_result": {"firing": False}, "final_health_status": "healthy"},
        recovered=True,
        checked_at=datetime.datetime.now(datetime.UTC)
    )
    db.add(verification)
    db.commit()
    db.close()
    
    # Second attempt should get 409
    response = client.post(f"/verification/run/{inc_id}")
    assert response.status_code == 409
    assert "already been performed" in response.json()["detail"].lower()
