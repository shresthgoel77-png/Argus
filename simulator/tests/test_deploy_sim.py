import pytest
import os
import subprocess
from fastapi.testclient import TestClient

from simulator.app import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown():
    # Reset config to clean state before test starts
    client.post("/simulate/reset")
    yield
    # Force reset config afterwards
    client.post("/simulate/reset")

def test_bad_deployment_flow():
    # 1. Trigger the regression
    resp1 = client.post("/simulate/bad-deployment")
    assert resp1.status_code == 200
    data = resp1.json()
    assert data["status"] == "bad_deployment_triggered"
    assert "commit_sha" in data
    
    # 2. Assert stacking is rejected
    resp2 = client.post("/simulate/bad-deployment")
    assert resp2.status_code == 409
    assert resp2.json()["status"] == "already_active"
    
    # 3. Assess local repo git log
    cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    git_log = subprocess.run(
        ["git", "log", "-1", "--format=%s"], 
        cwd=cwd, 
        capture_output=True, 
        text=True
    )
    assert "chore: tune payment gateway timeout and retry thresholds" in git_log.stdout
    
    # 4. Check degradation actually occurred on endpoint
    checkout_resp = client.get("/api/checkout")
    # Base latency is 1800ms
    assert checkout_resp.status_code in [200, 500]
    if checkout_resp.status_code == 200:
        assert checkout_resp.json()["latency_ms"] >= 1800
        
def test_reset_flow():
    client.post("/simulate/bad-deployment")
    
    # 1. Revert functionality
    resp = client.post("/simulate/reset")
    assert resp.status_code == 200
    assert resp.json()["status"] == "reset"
    
    # 2. Assert git log recorded revert
    cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    git_log = subprocess.run(
        ["git", "log", "-1", "--format=%s"], 
        cwd=cwd, 
        capture_output=True, 
        text=True
    )
    assert "revert: restore stable configuration" in git_log.stdout
    
    # 3. Validate state returned is healthy baseline
    state_resp = client.get("/simulate/state")
    assert state_resp.status_code == 200
    state_data = state_resp.json()
    assert state_data["bad_deployment_active"] is False
    assert state_data["config"]["error_rate"] == 0.0
