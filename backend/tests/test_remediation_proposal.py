import datetime
import os

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_incidents_remediation.db"

from app.main import app
from app.db import Base, SessionLocal, engine
from app.models import Evidence, Incident, RemediationAction

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.query(RemediationAction).delete()
    db.query(Evidence).delete()
    db.query(Incident).delete()
    db.commit()
    db.close()
    yield
    db = SessionLocal()
    db.query(RemediationAction).delete()
    db.query(Evidence).delete()
    db.query(Incident).delete()
    db.commit()
    db.close()

def _create_rca_complete_incident():
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

    ev = Evidence(
        incident_id=incident.id,
        category="ai_rca",
        content={
            "summary": "test",
            "impact": "test",
            "affected_components": [],
            "root_cause": "test",
            "confidence": "high",
            "supporting_evidence": [],
            "alternative_hypotheses": [],
            "recommended_fix": "test",
            "recommended_remediation": {
                "action_type": "restart_service",
                "params": {},
                "rationale": "fixes it"
            }
        },
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    iid = incident.id
    db.close()
    return iid

def test_propose_remediation_success():
    iid = _create_rca_complete_incident()
    response = client.post(f"/remediation/propose/{iid}")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["action_type"] == "restart_service"
    assert data["risk_level"] == "medium"
    assert data["status"] == "pending_approval"
    
    db = SessionLocal()
    inc = db.get(Incident, iid)
    assert inc.status == "remediation_proposed"
    db.close()

def test_double_propose_returns_409():
    iid = _create_rca_complete_incident()
    client.post(f"/remediation/propose/{iid}")
    response = client.post(f"/remediation/propose/{iid}")
    assert response.status_code == 409

def test_propose_on_not_rca_complete():
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
    
    response = client.post(f"/remediation/propose/{iid}")
    assert response.status_code == 409

def test_approve_remediation_success():
    iid = _create_rca_complete_incident()
    res = client.post(f"/remediation/propose/{iid}").json()
    action_id = res["id"]
    
    response = client.post(f"/remediation/{action_id}/approve", json={"approved_by": "alice"})
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["approved_by"] == "alice"
    
    # second approve -> 409
    response2 = client.post(f"/remediation/{action_id}/approve", json={"approved_by": "bob"})
    assert response2.status_code == 409

def test_reject_remediation_success():
    iid = _create_rca_complete_incident()
    res = client.post(f"/remediation/propose/{iid}").json()
    action_id = res["id"]
    
    response = client.post(f"/remediation/{action_id}/reject", json={"rejected_by": "charlie"})
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    
    db = SessionLocal()
    inc = db.get(Incident, iid)
    assert inc.status == "remediation_rejected"
    db.close()
    
    # second reject -> 409
    response2 = client.post(f"/remediation/{action_id}/reject", json={"rejected_by": "dan"})
    assert response2.status_code == 409

def test_unexpected_params_rejected():
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

    ev = Evidence(
        incident_id=incident.id,
        category="ai_rca",
        content={
            "recommended_remediation": {
                "action_type": "restart_service",
                "params": {"some_bad_key": 123},
                "rationale": "bad params"
            }
        },
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    iid = incident.id
    db.close()
    
    response = client.post(f"/remediation/propose/{iid}")
    assert response.status_code == 400
    assert "not allowed" in response.json()["detail"]
    
    db = SessionLocal()
    inc = db.get(Incident, iid)
    assert inc.status == "rca_complete" # Make sure it didn't change
    db.close()
