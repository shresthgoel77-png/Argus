import pytest
import os
import time
import datetime
import requests

# Disable background loop polling and use isolated test DB during tests
os.environ["DETECTION_POLL_INTERVAL_SECONDS"] = "3600"
os.environ["DATABASE_URL"] = "sqlite:///./test_incidents_investigation.db"
os.environ["PROMETHEUS_URL"] = "http://localhost:9090"
os.environ["LOKI_URL"] = "http://localhost:3100"

from fastapi.testclient import TestClient
from app.main import app
from app.db import Base, engine, SessionLocal
from app.models import Incident, Evidence
from app.investigation.metrics_evidence import collect_metrics_evidence
from app.investigation.logs_evidence import collect_logs_evidence
import app.observability.prometheus_client as prom_client
import app.observability.loki_client as loki_client

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

def test_investigation_collectors_e2e(monkeypatch):
    try:
        requests.get(f"{SIMULATOR_URL}/health", timeout=2.0)
    except requests.exceptions.RequestException as e:
        pytest.skip(f"Simulator not available at {SIMULATOR_URL}: {e}")
        
    try:
        requests.get(os.environ.get("LOKI_URL", "http://localhost:3100"), timeout=1.0)
    except requests.exceptions.RequestException:
        pytest.skip("Loki not available")

    # 1. Healthy state
    requests.post(f"{SIMULATOR_URL}/simulate/reset")
    generate_traffic(70)

    # Trigger bad deployment
    requests.post(f"{SIMULATOR_URL}/simulate/bad-deployment")
    generate_traffic(70)

    # 3. Detection pass
    new_incidents = []
    for _ in range(5):
        res = client.post("/detection/run")
        new_incidents = res.json()["new_incidents"]
        if len(new_incidents) > 0:
            break
        generate_traffic(3)

    assert len(new_incidents) > 0, "Bad deployment should fire detectors and create incidents"

    db = SessionLocal()
    incident_id = new_incidents[0]["id"]
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    assert incident is not None

    # Test metrics extraction
    metrics_evidence = collect_metrics_evidence(incident, db)
    
    assert len(metrics_evidence) == 3
    found_error_rate = False
    
    # At least one signal must have data
    assert any(len(ev.content["datapoints"]) > 0 for ev in metrics_evidence)
    
    for ev in metrics_evidence:
        assert ev.category == "observed_fact"
        if ev.content["signal"] == "error_rate" and len(ev.content["datapoints"]) > 0:
            found_error_rate = True
            assert ev.content["peak_value"] > 0
    assert found_error_rate

    # Test logs extraction
    logs_evidence = collect_logs_evidence(incident, db)
    assert len(logs_evidence) == 1
    log_ev = logs_evidence[0]
    assert log_ev.category == "observed_fact"
    assert "logql" in log_ev.content
    assert "window" in log_ev.content
    assert "matched_lines" in log_ev.content
    assert len(log_ev.content["matched_lines"]) > 0
    assert "timestamp" in log_ev.content["matched_lines"][0]

    # Clean up
    requests.post(f"{SIMULATOR_URL}/simulate/reset")
    db.close()


def test_collectors_unreachable_robustness(monkeypatch):
    import datetime
    # Setup dummy incident
    db = SessionLocal()
    incident = Incident(
        type="webhook_failure",
        service="simulator",
        severity="high",
        status="open",
        timestamp=datetime.datetime.utcnow()
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)

    # Verify Prom error
    monkeypatch.setenv("PROMETHEUS_URL", "http://localhost:19283")

    ev_metrics = collect_metrics_evidence(incident, db)
    for ev in ev_metrics:
        assert ev.category == "collection_error"

    # Verify loki error
    monkeypatch.setenv("LOKI_URL", "http://localhost:19284")

    ev_logs = collect_logs_evidence(incident, db)
    assert len(ev_logs) == 1
    assert ev_logs[0].category == "collection_error"
    
    db.close()
