import os
from datetime import datetime, timedelta, timezone

os.environ["DETECTION_POLL_INTERVAL_SECONDS"] = "3600"
os.environ["DATABASE_URL"] = "sqlite:///./test_incidents.db"

from fastapi.testclient import TestClient
from app.main import app
import app.detection.engine as detection_engine

client = TestClient(app)

def test_detection_status_reports_real_manual_pass(monkeypatch):
    monkeypatch.setattr(detection_engine, "detection_status", detection_engine.DetectionStatus(poll_interval_seconds=3600))
    assert client.get("/detection/status").json()["last_run_at"] is None
    for name in ("detect_high_error_rate", "detect_high_latency", "detect_webhook_failure"):
        monkeypatch.setattr(detection_engine.detectors, name, lambda service: {"firing": False})
    run = client.post("/detection/run")
    assert run.status_code == 200
    status = client.get("/detection/status").json()
    assert datetime.fromisoformat(status["last_run_at"]) > datetime.now(timezone.utc) - timedelta(seconds=5)
    assert status["last_run_new_incidents"] == len(run.json()["new_incidents"])
