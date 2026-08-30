import datetime
import os
import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_remediation_execution.db"
# Ensure we point to the running simulator for success case
os.environ["SIMULATOR_URL"] = "http://localhost:9000"

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

def _create_approved_action(action_type="rollback_deployment"):
    db = SessionLocal()
    incident = Incident(
        type="bad_deployment",
        service="simulator",
        severity="high",
        status="remediation_proposed",
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)

    action = RemediationAction(
        incident_id=incident.id,
        action_type=action_type,
        params={},
        risk_level="medium",
        approved=True,
        approved_by="test_user",
        status="approved"
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    
    iid = incident.id
    aid = action.id
    db.close()
    
    return iid, aid

def test_execute_success():
    # 1. Trigger bad deployment so the simulator is in a bad state
    import httpx
    # Ensure simulator is bad
    httpx.post("http://localhost:9000/simulate/bad-deployment")
    
    iid, aid = _create_approved_action("rollback_deployment")
    
    # 2. Execute the action
    response = client.post(f"/remediation/{aid}/execute")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["action"]["status"] == "executed"
    assert data["result"]["success"] is True
    assert "commit_sha" in data["result"]
    
    # 3. Verify incident state changed
    db = SessionLocal()
    inc = db.get(Incident, iid)
    assert inc.status == "remediated"
    db.close()
    
    # 4. Verify simulator state is actually fixed
    sim_state = httpx.get("http://localhost:9000/simulate/state").json()
    assert sim_state["bad_deployment_active"] is False

def test_execute_unsupported_action():
    iid, aid = _create_approved_action("restart_service")
    response = client.post(f"/remediation/{aid}/execute")
    
    assert response.status_code == 501
    
    db = SessionLocal()
    inc = db.get(Incident, iid)
    # Incident status should be unchanged
    assert inc.status == "remediation_proposed"
    act = db.get(RemediationAction, aid)
    assert act.status == "execution_unsupported"
    db.close()

def test_execute_simulator_unreachable(monkeypatch):
    monkeypatch.setenv("SIMULATOR_URL", "http://localhost:9999")
    iid, aid = _create_approved_action("rollback_deployment")
    
    response = client.post(f"/remediation/{aid}/execute")
    
    # Should get 502 Bad Gateway mapping
    assert response.status_code == 502
    
    db = SessionLocal()
    inc = db.get(Incident, iid)
    # Incident stays 'remediating'
    assert inc.status == "remediating"
    act = db.get(RemediationAction, aid)
    assert act.status == "execution_failed"
    assert act.result["success"] is False
    assert "error" in act.result
    db.close()

def test_execute_non_approved_action():
    db = SessionLocal()
    incident = Incident(
        type="bad_deployment",
        service="simulator",
        status="remediation_proposed",
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)

    action = RemediationAction(
        incident_id=incident.id,
        action_type="rollback_deployment",
        params={},
        risk_level="medium",
        approved=False,
        status="pending_approval"
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    aid = action.id
    db.close()
    
    response = client.post(f"/remediation/{aid}/execute")
    assert response.status_code == 409
