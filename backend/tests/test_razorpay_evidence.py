import pytest
import os
import time
import datetime
import requests

from app.db import Base, engine, SessionLocal
from app.models import Incident, Evidence
from app.investigation.razorpay_evidence import collect_razorpay_evidence
from app.investigation.engine import run_investigation

SIMULATOR_URL = os.getenv("SIMULATOR_URL", "http://localhost:9000")

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

def wait_for_simulator():
    try:
        requests.get(f"{SIMULATOR_URL}/health", timeout=2.0)
    except requests.exceptions.RequestException as e:
        pytest.skip(f"Simulator not available at {SIMULATOR_URL}: {e}")

def get_db():
    return SessionLocal()

def test_razorpay_tampered_traffic():
    wait_for_simulator()
    db = get_db()
    
    # 1. Real tampered traffic
    incident = Incident(
        type="webhook_failure",
        service="simulator",
        severity="high",
        status="open",
        timestamp=datetime.datetime.utcnow() - datetime.timedelta(seconds=15)
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)

    # Trigger tampered webhooks
    for _ in range(5):
        requests.post(f"{SIMULATOR_URL}/simulate/razorpay-webhook?variant=tampered")
        time.sleep(0.5)

    # Allow Prometheus to scrape and index
    time.sleep(5)
    
    evidence = collect_razorpay_evidence(incident, db)
    
    assert len(evidence) == 2
    for ev in evidence:
        assert ev.category == "observed_fact"
    
    # We should see a peak in razorpay_signature_failure_rate
    signature_evidence = next(ev for ev in evidence if ev.content["signal"] == "razorpay_signature_failure_rate")
    assert len(signature_evidence.content["datapoints"]) > 0
    assert signature_evidence.content["peak_value"] > 0
    
    db.close()

def test_razorpay_no_traffic():
    wait_for_simulator()
    db = get_db()
    
    # Wait to ensure no fresh events in the current window
    time.sleep(2)
    
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

    evidence = collect_razorpay_evidence(incident, db)
    assert len(evidence) == 2
    
    # Assert values are real zeroes, not skipped
    for ev in evidence:
        assert ev.category == "observed_fact"
        assert len(ev.content["datapoints"]) > 0
        assert ev.content["peak_value"] == 0.0
        
    db.close()

def test_razorpay_wrong_incident_type(monkeypatch):
    wait_for_simulator()
    db = get_db()
    
    # Monkeypatch to ensure no calls are made
    def mock_range_query(*args, **kwargs):
        raise RuntimeError("Should not have been called!")
        
    monkeypatch.setattr("app.investigation.razorpay_evidence.range_query", mock_range_query)
    
    incident = Incident(
        type="high_error_rate",
        service="simulator",
        severity="high",
        status="open",
        timestamp=datetime.datetime.utcnow()
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    
    evidence = collect_razorpay_evidence(incident, db)
    assert evidence == []
    
    db.close()

def test_razorpay_engine_integration():
    wait_for_simulator()
    db = get_db()
    
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

    result = run_investigation(incident.id, db)
    
    # Engine should return the 2 razorpay signals in observed_facts
    # Total facts: 3 metrics + 1 log + 2 razorpay + maybe git = 6+
    observed_facts = result["observed_facts"]
    
    razorpay_signals = [f for f in observed_facts if "signal" in f and f["signal"].startswith("razorpay_")]
    assert len(razorpay_signals) == 2
    
    db.close()
