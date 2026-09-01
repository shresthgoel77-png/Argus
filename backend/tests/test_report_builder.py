import datetime
import os
import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_report_builder.db"

from app.main import app
from app.db import Base, SessionLocal, engine
from app.models import Incident, Evidence, RemediationAction, VerificationResult

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.query(VerificationResult).delete()
    db.query(RemediationAction).delete()
    db.query(Evidence).delete()
    db.query(Incident).delete()
    db.commit()
    db.close()
    yield
    db = SessionLocal()
    db.query(VerificationResult).delete()
    db.query(RemediationAction).delete()
    db.query(Evidence).delete()
    db.query(Incident).delete()
    db.commit()
    db.close()

def _create_incident(status="resolved", include_rca=True, include_remediation=True, include_verification=True):
    db = SessionLocal()
    
    # 1. Base incident
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
    
    # 2. Base evidence (Metrics, Logs, Git)
    metrics_ev = Evidence(
        incident_id=inc_id,
        category="metrics",
        content={"signal": "error_rate", "datapoints": [[timestamp.timestamp(), 0.15]]}
    )
    logs_ev = Evidence(
        incident_id=inc_id,
        category="logs",
        content={"matched_lines": [{"timestamp": timestamp.timestamp(), "line": "Error processing request"}, 
                                   {"timestamp": timestamp.timestamp() + 1, "line": "Database connection failed"}]}
    )
    git_ev = Evidence(
        incident_id=inc_id,
        category="git",
        content={"commits": [{"sha": "f8a19bcde", "message": "Deploy broken changes", "timestamp": timestamp.isoformat(), "files": ["app.js", "style.css"]}]}
    )
    db.add_all([metrics_ev, logs_ev, git_ev])
    db.commit()
    db.refresh(metrics_ev)
    db.refresh(logs_ev)
    db.refresh(git_ev)
    
    # 3. AI RCA
    if include_rca:
        ai_rca_ev = Evidence(
            incident_id=inc_id,
            category="ai_rca",
            content={
                "summary": "High error rate due to broken deployment.",
                "impact": "Users cannot checkout.",
                "affected_components": ["checkout_service", "database_layer"],
                "root_cause": "A recent commit introduced a typo in the DB query.",
                "confidence": "high",
                "supporting_evidence": [str(metrics_ev.id), str(logs_ev.id), str(git_ev.id)],
                "alternative_hypotheses": ["Network partition (rejected)"],
                "recommended_fix": "Roll back the latest deployment.",
                "recommended_remediation": {
                    "action_type": "rollback_deployment",
                    "params": {},
                    "rationale": "Safest way to restore service."
                }
            }
        )
        db.add(ai_rca_ev)
        db.commit()
    
    # 4. Remediation
    if include_remediation:
        action = RemediationAction(
            incident_id=inc_id,
            action_type="rollback_deployment",
            params={},
            risk_level="medium",
            approved=True,
            approved_by="sre_bot",
            status="executed",
            executed_at=timestamp + datetime.timedelta(minutes=5),
            result={"success": True, "commit_sha": "a1b2c3d4e"}
        )
        db.add(action)
        db.commit()
        
    # 5. Verification
    if include_verification:
        vr = VerificationResult(
            incident_id=inc_id,
            before_metrics={"firing": True, "value": 0.15},
            after_metrics={"final_detector_result": {"firing": False, "value": 0.0}, "final_health_status": "healthy"},
            recovered=True,
            checked_at=timestamp + datetime.timedelta(minutes=10)
        )
        db.add(vr)
        db.commit()
        
    db.close()
    return inc_id

# -----------------
# Tests
# -----------------

def test_full_resolved_incident_report():
    """Test 1: Full resolved incident report gives all populated real data."""
    inc_id = _create_incident(status="resolved", include_rca=True, include_remediation=True, include_verification=True)
    
    response = client.get(f"/incidents/{inc_id}/report")
    assert response.status_code == 200
    
    data = response.json()
    assert "markdown" in data
    assert "generated_at" in data
    
    markdown = data["markdown"]
    
    # Check that real text is in the standard report format
    assert "# Incident Report: bad_deployment — simulator (high)" in markdown
    assert "A recent commit introduced a typo in the DB query." in markdown  # root cause
    assert "High" in markdown or "high" in markdown  # confidence
    assert "f8a19bc" in markdown  # original broken commit SHA
    assert "rollback_deployment" in markdown  # action type
    assert "a1b2c3d4e" in markdown  # executed rollback commit SHA (remediation result)
    assert "Recovery verified." in markdown  # verification result (recovered=True)

def test_rca_complete_only_report():
    """Test 2: RCA-complete incident (no remediation/verification yet) shows honest omit text."""
    inc_id = _create_incident(status="rca_complete", include_rca=True, include_remediation=False, include_verification=False)
    
    response = client.get(f"/incidents/{inc_id}/report")
    assert response.status_code == 200
    
    markdown = response.json()["markdown"]
    
    # Honest omission strings
    assert "No remediation action has been proposed yet." in markdown
    assert "Verification has not been run yet." in markdown
    
    # Real AI RCA text should still be present
    assert "A recent commit introduced a typo in the DB query." in markdown

def test_409_before_rca():
    """Test 3: Requesting a report before RCA completes returns 409."""
    # Create incident with NO AI RCA evidence
    inc_id = _create_incident(status="investigated", include_rca=False, include_remediation=False, include_verification=False)
    
    response = client.get(f"/incidents/{inc_id}/report")
    assert response.status_code == 409
    assert "Report requires RCA to be completed first" in response.json()["detail"]

def test_404_unknown_incident():
    """Test 4: Requesting a report for a missing incident returns 404."""
    response = client.get("/incidents/999/report")
    assert response.status_code == 404
    assert "Incident not found" in response.json()["detail"]
