import datetime
import os
import time
import httpx
import pytest

from app.db import Base, SessionLocal, engine
from app.models import Incident, VerificationResult, RemediationAction
from app.verification.engine import (
    VerificationStateError,
    run_verification,
)
from app.detection.engine import run_detection_pass
from app.remediation.handlers import handle_rollback_deployment

os.environ["DATABASE_URL"] = "sqlite:///./test_verification.db"
os.environ["SIMULATOR_URL"] = "http://localhost:9000"
os.environ["PROMETHEUS_URL"] = "http://localhost:9090"

@pytest.fixture(autouse=True)
def db_session_fixture():
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

def make_incident(status="remediated", incident_type="high_error_rate", initial_metrics=None):
    session = SessionLocal()
    if initial_metrics is None:
        initial_metrics = {"value": 12.5, "firing": True}
        
    incident = Incident(
        type=incident_type,
        service="simulator",
        severity="high",
        timestamp=datetime.datetime.now(datetime.UTC),
        trigger="test",
        status=status,
        initial_metrics=initial_metrics,
    )
    session.add(incident)
    session.commit()
    session.refresh(incident)
    inc_id = incident.id
    session.close()
    return inc_id


def test_real_recovery_flow(monkeypatch):
    """
    Real Phase 3 -> Rollback -> Traffic -> Verification flow.
    No mocking of DETECTOR_BY_INCIDENT_TYPE or _check_simulator_health.
    """
    # Use real settings to allow polling (must cover prometheus scrape interval)
    monkeypatch.setenv("VERIFICATION_MAX_WAIT_SECONDS", "60")
    monkeypatch.setenv("VERIFICATION_POLL_INTERVAL_SECONDS", "2")
    monkeypatch.setenv("DETECTION_WINDOW", "15s")
    monkeypatch.setenv("ERROR_RATE_MEDIUM", "0.05")

    # 1. Start clean, then trigger bad deployment
    httpx.post(f"{os.environ['SIMULATOR_URL']}/simulate/reset", timeout=5.0)
    httpx.post(f"{os.environ['SIMULATOR_URL']}/simulate/bad-deployment", timeout=5.0)
    
    # 2. Generate traffic so Prometheus has failing data
    generate_traffic(15.0)
    
    # 3. Detect incident natively so we get real initial_metrics
    session = SessionLocal()
    detection_res = run_detection_pass(session, "simulator")
    
    assert len(detection_res) > 0, "Expected detection pass to detect a high error rate incident!"
    sim_incident_id = detection_res[0].id
    session.close()
    
    # Check that initial metrics are real (i.e. not mocked zero values)
    session = SessionLocal()
    incident = session.query(Incident).filter(Incident.id == sim_incident_id).first()
    assert incident, "Detected incident must exist."
    assert incident.initial_metrics.get("firing") is True, f"Initial metrics should be firing: {incident.initial_metrics}"
    assert incident.initial_metrics.get("value", 0.0) > 0.0, f"Value shouldn't be zero: {incident.initial_metrics}"
    
    # Fast-forward incident to 'remediated' status simulating RCA+propose+approve
    incident.status = "remediating"
    session.commit()
    session.close()
    
    # 4. Execute the Rollback Action (real remediation handler)
    action = RemediationAction(
        incident_id=sim_incident_id,
        action_type="rollback_deployment",
        params={},
        risk_level="medium",
        approved=True,
        approved_by="test_user",
        status="approved"
    )
    result = handle_rollback_deployment(action)
    assert result["success"] is True, "Rollback handler failed."
    
    session = SessionLocal()
    incident = session.query(Incident).filter(Incident.id == sim_incident_id).first()
    incident.status = "remediated"
    session.commit()
    session.close()

    import threading
    # 5. Generate healthy traffic while run_verification() polls (per requirements)
    traffic_thread = threading.Thread(target=generate_traffic, args=(50.0,))
    traffic_thread.start()
    
    # Give it a second to hit prometheus before verification starts
    time.sleep(1.0)
    
    # 6. Run verification on real test harness
    session = SessionLocal()
    verification_result = run_verification(sim_incident_id, session)
    traffic_thread.join()
    
    assert verification_result["recovered"] is True
    # before_metrics should match the real metrics caught at detection
    assert verification_result["before_metrics"]["firing"] is True
    assert verification_result["before_metrics"]["value"] > 0.0
    
    # after_metrics should show a non-firing recovery
    assert verification_result["after_metrics"]["final_detector_result"]["firing"] is False
    assert verification_result["after_metrics"]["final_health_status"] == "healthy"
    assert len(verification_result["after_metrics"]["poll_history"]) >= 1
    
    # DB state transitions
    incident = session.query(Incident).filter(Incident.id == sim_incident_id).first()
    assert incident.status == "resolved"
    assert session.query(VerificationResult).count() == 1
    session.close()


def test_real_non_recovery(monkeypatch):
    """
    Tests the flow when the service stays broken. 
    Uses real short timeout without mocking detectors.
    """
    monkeypatch.setenv("VERIFICATION_MAX_WAIT_SECONDS", "5")
    monkeypatch.setenv("VERIFICATION_POLL_INTERVAL_SECONDS", "2")
    monkeypatch.setenv("DETECTION_WINDOW", "15s")
    
    # 1. Trigger bad deployment and leave it broken
    httpx.post(f"{os.environ['SIMULATOR_URL']}/simulate/bad-deployment", timeout=5.0)
    
    # 2. Build some bad traffic
    generate_traffic(10.0)
    
    # 3. Simulate an incident hitting the "remediated" phase even though it wasn't actually fixed
    session = SessionLocal()
    detection_res = run_detection_pass(session, "simulator")
    if len(detection_res) > 0:
        sim_incident_id = detection_res[0].id
        inci = session.query(Incident).filter(Incident.id == sim_incident_id).first()
        inci.status = "remediated"
        session.commit()
    else:
        # Fallback if detection took longer: mock the incident DB row, but let verification run real prometheus
        sim_incident_id = make_incident(status="remediated", incident_type="high_error_rate")
    session.close()
    
    # 4. Generate a little more failing traffic during verify start
    generate_traffic(2.0)
    
    # 5. Verify against failing system
    session = SessionLocal()
    verification_result = run_verification(sim_incident_id, session)
    
    assert verification_result["recovered"] is False
    assert verification_result["after_metrics"]["final_detector_result"]["firing"] is True
    
    incident = session.query(Incident).filter(Incident.id == sim_incident_id).first()
    assert incident.status == "remediation_failed"
    session.close()


def test_verification_requires_remediated_incident():
    inc_id = make_incident(status="remediating")
    
    session = SessionLocal()
    with pytest.raises(VerificationStateError, match="must be remediated"):
        run_verification(inc_id, session)
    session.close()


def test_verification_is_one_shot():
    inc_id = make_incident()
    session = SessionLocal()
    # Add a mock older verification
    session.add(
        VerificationResult(
            incident_id=inc_id,
            before_metrics={},
            after_metrics={},
            recovered=True,
        )
    )
    session.commit()

    with pytest.raises(VerificationStateError, match="already been performed"):
        run_verification(inc_id, session)
    session.close()


def test_transient_prometheus_failure_is_recorded_and_polling_continues(monkeypatch):
    inc_id = make_incident()
    from app.observability.prometheus_client import PrometheusUnavailableError

    # We mock the detector ONLY to inject the exact exception, as stopping the real prometheus container in the middle of a test is unsafe for other tests
    detector_results = iter(
        [
            PrometheusUnavailableError("Prometheus down"),
            {"firing": False, "value": 0.2, "severity": None},
            {"firing": False, "value": 0.2, "severity": None}, # the zero value requires 2 polls minimum if zero, but since value=0.2 it breaks immediately on poll 2
        ]
    )

    def detector(service):
        result = next(detector_results)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(
        "app.verification.engine.DETECTOR_BY_INCIDENT_TYPE",
        {"high_error_rate": detector},
    )
    monkeypatch.setattr("app.verification.engine._check_simulator_health", lambda: "healthy")
    monkeypatch.setenv("VERIFICATION_MAX_WAIT_SECONDS", "2")
    monkeypatch.setenv("VERIFICATION_POLL_INTERVAL_SECONDS", "0")

    session = SessionLocal()
    result = run_verification(inc_id, session)

    assert result["recovered"] is True
    assert result["after_metrics"]["poll_history"][0]["detector_result"]["error"] == "Prometheus down"
    session.close()
