import pytest
import os
import time
import datetime
import requests

# Disable background loop polling and use isolated test DB during tests
os.environ["DETECTION_POLL_INTERVAL_SECONDS"] = "3600"
os.environ["DATABASE_URL"] = "sqlite:///./test_incidents.db"
os.environ["PROMETHEUS_URL"] = "http://localhost:9090"
os.environ["LOKI_URL"] = "http://localhost:3100"

from fastapi.testclient import TestClient
from app.main import app
from app.db import Base, engine, SessionLocal
from app.models import Incident
import app.detection.cooldown as cd

SIMULATOR_URL = os.getenv("SIMULATOR_URL", "http://localhost:9000")
client = TestClient(app)

def generate_traffic(seconds: int):
    end_time = time.time() + seconds
    while time.time() < end_time:
        try:
            requests.get(f"{SIMULATOR_URL}/api/checkout", timeout=1.0)
            requests.post(f"{SIMULATOR_URL}/webhook/payment-event", json={}, timeout=1.0)
        except requests.exceptions.RequestException:
            pass
        time.sleep(0.5)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.query(Incident).delete()
    db.commit()
    db.close()
    yield
    db = SessionLocal()
    db.query(Incident).delete()
    db.commit()
    db.close()


def test_detection_engine_e2e(monkeypatch):
    import app.observability.prometheus_client as prom_client
    prom_client.PROMETHEUS_URL = "http://localhost:9090"
    
    try:
        requests.get(f"{SIMULATOR_URL}/health", timeout=2.0)
    except requests.exceptions.RequestException as e:
        pytest.skip(f"Simulator not available at {SIMULATOR_URL}: {e}")
        
    # 1. Healthy state check
    requests.post(f"{SIMULATOR_URL}/simulate/reset")
    generate_traffic(70)
    
    res = client.post("/detection/run")
    assert res.status_code == 200
    assert len(res.json()["new_incidents"]) == 0
    
    # 2. Trigger bad deployment
    requests.post(f"{SIMULATOR_URL}/simulate/bad-deployment")
    generate_traffic(70)
    
    # 3. Detection pass
    new_incidents = []
    for _ in range(5):
        res = client.post("/detection/run")
        new_incidents = res.json()["new_incidents"]
        
        # DEBUG PREVIEW
        import app.detection.detectors as dets
        print(f"DEBUG LOOP PASS: ERR={dets.detect_high_error_rate('simulator')} LAT={dets.detect_high_latency('simulator')}")
        
        if len(new_incidents) > 0:
            break
        generate_traffic(3)
        
    assert res.status_code == 200
    assert len(new_incidents) > 0, "Bad deployment should fire detectors and create incidents"
    
    # Verify fields
    assert new_incidents[0]["initial_metrics"]["value"] > 0
    assert new_incidents[0]["status"] == "open"
    assert new_incidents[0]["trigger"]
    
    # 4. Check deduplication on quick repeated run
    res_dedup = client.post("/detection/run")
    assert res_dedup.status_code == 200
    assert len(res_dedup.json()["new_incidents"]) == 0, "Already open incident must be deduplicated"
    
    # Verify GET works
    get_res = client.get("/incidents?status=open")
    assert get_res.status_code == 200
    assert len(get_res.json()) >= len(new_incidents)
    
    # 5. Check Cooldown
    db = SessionLocal()
    open_incident_id = new_incidents[0]["id"]
    db_incident = db.query(Incident).filter(Incident.id == open_incident_id).first()
    db_incident.status = "resolved"
    db_incident.resolved_at = datetime.datetime.utcnow()
    db.commit()
    
    # Mock cooldown actively preventing trigger
    monkeypatch.setattr(cd, "COOLDOWN_SECONDS", 3600)
    res_cooldown = client.post("/detection/run")
    assert len(res_cooldown.json()["new_incidents"]) == 0, "Cooldown should prevent re-firing"
    
    # Bypass cooldown mock to simulate expiry
    monkeypatch.setattr(cd, "COOLDOWN_SECONDS", 0)
    res_bypass = client.post("/detection/run")
    assert len(res_bypass.json()["new_incidents"]) > 0, "Expired cooldown should allow re-firing"
    
    db.close()
    
    # Cleanup simulator state
    requests.post(f"{SIMULATOR_URL}/simulate/reset")

def test_prometheus_unreachable_robustness(monkeypatch):
    import app.detection.detectors as dets
    def mock_instant_query(query):
        raise Exception("Prometheus is unreachable")
    
    monkeypatch.setattr(dets, "instant_query", mock_instant_query)
    
    # Engine should not crash 
    res = client.post("/detection/run")
    assert res.status_code == 200
    assert len(res.json()["new_incidents"]) == 0
