import datetime
import os
import time

import pytest
import requests


os.environ["DETECTION_POLL_INTERVAL_SECONDS"] = "3600"
os.environ["DATABASE_URL"] = "sqlite:///./test_incidents_investigation.db"
os.environ["PROMETHEUS_URL"] = "http://localhost:9090"
os.environ["LOKI_URL"] = "http://localhost:3100"

from fastapi.testclient import TestClient

from app.main import app
from app.db import Base, SessionLocal, engine
from app.models import Evidence, Incident
import app.investigation.engine as investigation_engine


SIMULATOR_URL = os.getenv("SIMULATOR_URL", "http://localhost:9000")
client = TestClient(app)


def generate_traffic(seconds: int) -> None:
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


def test_investigation_route_returns_404_and_409_without_collecting_evidence():
    missing_response = client.post("/investigation/run/999999")
    assert missing_response.status_code == 404

    db = SessionLocal()
    incident = Incident(
        type="high_error_rate",
        service="simulator",
        severity="high",
        status="investigated",
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    incident_id = incident.id
    db.close()

    duplicate_response = client.post(f"/investigation/run/{incident_id}")
    assert duplicate_response.status_code == 409


def test_investigation_correlates_fault_injection_commit(monkeypatch):
    try:
        requests.get(f"{SIMULATOR_URL}/health", timeout=2.0)
    except requests.exceptions.RequestException as error:
        pytest.skip(f"Simulator not available at {SIMULATOR_URL}: {error}")

    observed_statuses = []
    original_metrics_collector = investigation_engine.collect_metrics_evidence

    def track_investigating_status(incident, db_session):
        db_session.refresh(incident)
        observed_statuses.append(incident.status)
        return original_metrics_collector(incident, db_session)

    monkeypatch.setattr(
        investigation_engine, "collect_metrics_evidence", track_investigating_status
    )

    try:
        assert requests.post(f"{SIMULATOR_URL}/simulate/reset").status_code == 200
        generate_traffic(70)

        bad_deployment = requests.post(f"{SIMULATOR_URL}/simulate/bad-deployment")
        assert bad_deployment.status_code == 200
        fault_commit_sha = bad_deployment.json()["commit_sha"]
        generate_traffic(70)

        new_incidents = []
        for _ in range(5):
            detection_response = client.post("/detection/run")
            assert detection_response.status_code == 200
            new_incidents = detection_response.json()["new_incidents"]
            if new_incidents:
                break
            generate_traffic(3)
        assert new_incidents, "Bad deployment should create an incident"
        incident_id = new_incidents[0]["id"]

        investigation_response = client.post(f"/investigation/run/{incident_id}")
        assert investigation_response.status_code == 200
        result = investigation_response.json()

        git_fact = next(
            fact for fact in result["observed_facts"] if fact.get("source") == "git"
        )
        assert any(commit["sha"] == fault_commit_sha for commit in git_fact["commits"])
        assert any(
            fault_commit_sha[:7] in hypothesis["hypothesis"]
            for hypothesis in result["hypotheses"]
        )

        timestamps = [datetime.datetime.fromisoformat(entry["timestamp"]) for entry in result["correlations"]]
        assert timestamps == sorted(timestamps)
        assert "investigating" in observed_statuses

        db = SessionLocal()
        assert db.get(Incident, incident_id).status == "investigated"
        db.close()

        duplicate_response = client.post(f"/investigation/run/{incident_id}")
        assert duplicate_response.status_code == 409
        missing_response = client.post("/investigation/run/999999")
        assert missing_response.status_code == 404
    finally:
        requests.post(f"{SIMULATOR_URL}/simulate/reset")
