"""
Observability integration test.

Prerequisites:
  - Docker Compose stack running (prometheus + loki)
  - Simulator running on port 9000

Run manually:
  python -m pytest simulator/tests/test_observability.py -v -s
"""
import time
import requests
import pytest


SIMULATOR_URL = "http://localhost:9000"
PROMETHEUS_URL = "http://localhost:9090"
LOKI_URL = "http://localhost:3100"


def _is_service_up(url: str) -> bool:
    try:
        requests.get(url, timeout=2)
        return True
    except Exception:
        return False


def _prom_query(query: str):
    """Execute an instant PromQL query and return the result vector."""
    resp = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
    resp.raise_for_status()
    data = resp.json()
    assert data["status"] == "success", f"Prometheus query failed: {data}"
    return data["data"]["result"]





def test_prometheus_target_up():
    """Prometheus should show the simulator target as 'up'."""
    resp = requests.get(f"{PROMETHEUS_URL}/api/v1/targets")
    resp.raise_for_status()
    targets = resp.json()["data"]["activeTargets"]
    sim_targets = [t for t in targets if "simulator" in t.get("labels", {}).get("job", "")]
    assert len(sim_targets) > 0, "No simulator target found in Prometheus"
    assert sim_targets[0]["health"] == "up", f"Simulator target is not up: {sim_targets[0]}"


def test_prometheus_metrics_increase():
    """After sending requests, http_requests_total should increase."""
    # Get baseline
    before = _prom_query('http_requests_total{endpoint="/api/checkout"}')
    baseline = sum(float(r["value"][1]) for r in before) if before else 0

    # Generate traffic
    num_requests = 5
    for _ in range(num_requests):
        requests.get(f"{SIMULATOR_URL}/api/checkout")

    # Wait for scrape interval (5s) + buffer
    time.sleep(8)

    after = _prom_query('http_requests_total{endpoint="/api/checkout"}')
    current = sum(float(r["value"][1]) for r in after)
    assert current >= baseline + num_requests, (
        f"Expected at least {baseline + num_requests} total, got {current}"
    )


def test_loki_receives_logs():
    """Loki should contain log entries from the simulator."""
    # Generate a request so there's something to find
    requests.get(f"{SIMULATOR_URL}/api/checkout")
    time.sleep(3)  # Allow push + indexing

    # Query Loki
    resp = requests.get(
        f"{LOKI_URL}/loki/api/v1/query_range",
        params={
            "query": '{job="simulator"}',
            "limit": 10,
            "since": "5m",
        }
    )
    resp.raise_for_status()
    data = resp.json()
    streams = data.get("data", {}).get("result", [])
    assert len(streams) > 0, f"No log streams found in Loki for job=simulator. Response: {data}"

    # Verify at least one value exists
    total_entries = sum(len(s.get("values", [])) for s in streams)
    assert total_entries > 0, "Loki streams exist but contain no log entries"
