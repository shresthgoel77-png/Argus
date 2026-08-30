import json
import os
import pytest
from fastapi.testclient import TestClient

from simulator.app import app
from simulator.config import CONFIG_PATH, DEFAULT_CONFIG

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_config():
    # Ensure zero error rate before each test
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        cfg = DEFAULT_CONFIG.copy()
        cfg["error_rate"] = 0.0
        cfg["webhook_failure_rate"] = 0.0
        json.dump(cfg, f)
    yield
    # We could theoretically revert config back to defaults, but next test setup will overwrite anyway.

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_checkout_deterministic():
    for _ in range(5):
        response = client.get("/api/checkout")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "latency_ms" in data

def test_metrics_populates():
    # Hit checkout
    client.get("/api/checkout")
    
    # Check metrics text exposition
    response = client.get("/metrics")
    assert response.status_code == 200
    content = response.text
    assert "http_requests_total" in content
    assert "http_request_duration_seconds" in content
