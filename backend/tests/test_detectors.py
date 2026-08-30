"""
Tests for threshold-based detectors (Phase 2).
Requires the Phase 2 stack (fastapi backend + prometheus) + simulator running.
"""
import pytest
import os
import sys
import time
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


from app.detection import thresholds
from app.detection.detectors import detect_high_error_rate, detect_high_latency, detect_webhook_failure

# Simulator is likely at 8001
SIMULATOR_URL = os.getenv("SIMULATOR_URL", "http://localhost:9000")

def generate_traffic(seconds: int):
    end_time = time.time() + seconds
    while time.time() < end_time:
        try:
            requests.get(f"{SIMULATOR_URL}/api/checkout", timeout=1.0)
            requests.post(f"{SIMULATOR_URL}/webhook/payment-event", json={}, timeout=1.0)
        except requests.exceptions.RequestException:
            pass
        time.sleep(0.5)

def test_detectors_e2e():
    try:
        requests.get(f"{SIMULATOR_URL}/health", timeout=2.0)
    except requests.exceptions.RequestException as e:
        pytest.skip(f"Simulator not available at {SIMULATOR_URL}: {e}")

    # 1. Reset
    requests.post(f"{SIMULATOR_URL}/simulate/reset")
    # Generate some healthy traffic and give it time to scrape
    generate_traffic(70)
    
    # Check baseline (should be firing=False, value real low numbers or 0.0)
    res_err = detect_high_error_rate("simulator")
    res_lat = detect_high_latency("simulator")
    res_hook = detect_webhook_failure("simulator")
    
    assert not res_err["firing"], f"Baseline err fired: {res_err}"
    assert not res_lat["firing"], f"Baseline lat fired: {res_lat}"
    assert not res_hook["firing"], f"Baseline hook fired: {res_hook}"
    
    # 2. Trigger bad deployment
    res = requests.post(f"{SIMULATOR_URL}/simulate/bad-deployment")
    assert res.status_code in (200, 409)
    
    # Generate traffic for ~70s to ensure Prometheus scrapes it and rate() computes over 1m window
    generate_traffic(70)
    
    # 3. Assert detection
    res_err_bad = detect_high_error_rate("simulator")
    res_lat_bad = detect_high_latency("simulator")
    
    assert res_err_bad["firing"], f"Should have detected high error rate: {res_err_bad}"
    assert res_lat_bad["firing"], f"Should have detected high latency: {res_lat_bad}"
    assert res_err_bad["severity"] in ["medium", "high"]
    assert res_lat_bad["severity"] in ["medium", "high"]
    
    # 4. Reset again
    requests.post(f"{SIMULATOR_URL}/simulate/reset")
    
    # Wait for the bad data to fall out of the window by generating healthy traffic
    generate_traffic(75)
    
    res_err_reset = detect_high_error_rate("simulator")
    # Should recover back to False
    assert not res_err_reset["firing"], f"Should recover: {res_err_reset}"
