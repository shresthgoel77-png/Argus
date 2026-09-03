import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Import backend app modules FIRST so 'app' in sys.modules points to backend/app
from app.models import Incident, Evidence, RemediationAction, VerificationResult
from app.db import SessionLocal

# Then add simulator dir
SIMULATOR_DIR = PROJECT_ROOT / "simulator"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))
if str(SIMULATOR_DIR) not in sys.path:
    sys.path.insert(0, str(SIMULATOR_DIR))

from simulator.app import app as simulator_app

from simulator.app import app as simulator_app
sim_client = TestClient(simulator_app)


def add_fake_data(db):
    inc = Incident(type="fake_type", service="fake_service", severity="low", status="open")
    db.add(inc)
    db.commit()
    db.refresh(inc)
    
    ev = Evidence(incident_id=inc.id, category="fake", content={})
    ra = RemediationAction(incident_id=inc.id, action_type="fake", params={}, risk_level="low", status="approved")
    vr = VerificationResult(incident_id=inc.id, recovered=True)
    
    db.add(ev)
    db.add(ra)
    db.add(vr)
    db.commit()
    return inc.id


def test_demo_reset_403_when_disabled(security_db, monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    client = security_db
    
    with SessionLocal() as db:
        add_fake_data(db)
        
    res = client.post("/demo/reset-data")
    assert res.status_code == 403
    
    # Verify data remains
    with SessionLocal() as db:
        assert db.query(Incident).count() == 1


def test_demo_reset_clears_data(security_db, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    client = security_db
    
    with SessionLocal() as db:
        add_fake_data(db)
        
    res = client.post("/demo/reset-data")
    assert res.status_code == 200
    assert res.json()["status"] == "reset"
    assert "incidents" in res.json()["tables_cleared"]
    
    # Verify data cleared
    with SessionLocal() as db:
        assert db.query(Incident).count() == 0
        assert db.query(Evidence).count() == 0
        assert db.query(RemediationAction).count() == 0
        assert db.query(VerificationResult).count() == 0
        
    # Resetting detection_status
    from app.detection.engine import detection_status
    assert detection_status.last_run_at is None
    assert detection_status.last_run_new_incidents == 0

    # Ensure simulator was effectively reset
    state_res = sim_client.get("/simulate/state")
    assert state_res.status_code == 200
    assert state_res.json()["bad_deployment_active"] is False


def test_simulator_warm_up():
    def get_checkout_count():
        res = sim_client.get("/metrics")
        count = 0.0
        for line in res.text.split("\n"):
            if line.startswith('http_requests_total{endpoint="/api/checkout"'):
                try:
                    count += float(line.split()[1])
                except Exception:
                    pass
        return count

    initial_count = get_checkout_count()

    res = sim_client.post("/simulate/warm-up?requests=10")
    assert res.status_code == 200
    data = res.json()
    assert data["requests_sent"] == 10
    
    summary = data["results_summary"]
    assert "2xx" in summary
    assert "5xx" in summary
    assert summary["2xx"] + summary["5xx"] == 10

    final_count = get_checkout_count()
    assert (final_count - initial_count) == 10
