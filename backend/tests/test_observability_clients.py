import os
import pytest
from datetime import datetime, timedelta, timezone

from app.observability.prometheus_client import (
    instant_query,
    range_query,
    PrometheusUnavailableError
)
from app.observability.loki_client import (
    query_range,
    LokiUnavailableError
)

# =================================================================================
# DEPENDENCY NOTE:
# These tests are integration-style and require the Phase 2 Prompt 1 stack running 
# (Prometheus on localhost:9090 and Loki on localhost:3100), as well as the 
# simulator having served some recent traffic to generate actual metrics and logs.
# =================================================================================

def test_prometheus_instant_query_success():
    """
    Test that instant_query("up") returns a non-empty result reflecting 
    the real scrape target status.
    """
    import requests
    try:
        requests.get(os.environ.get("PROMETHEUS_URL", "http://localhost:9090"), timeout=1.0)
    except requests.exceptions.RequestException:
        pytest.skip("Prometheus not available")
    # Ensure PROMETHEUS_URL is correct or falls back to default
    result = instant_query("up")
    
    # Assert result is a list and has items
    assert isinstance(result, list), "Result should be a list"
    assert len(result) > 0, "Query 'up' should return at least one scrape target status"
    
    # Check shape of returning data
    first_target = result[0]
    assert "metric" in first_target
    assert "value" in first_target

def test_prometheus_range_query_success():
    """
    Test that range_query on http_requests_total over the last 5 minutes 
    returns real datapoints.
    """
    import requests
    try:
        requests.get(os.environ.get("PROMETHEUS_URL", "http://localhost:9090"), timeout=1.0)
    except requests.exceptions.RequestException:
        pytest.skip("Prometheus not available")
        
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=5)
    
    result = range_query("http_requests_total", start, end)
    
    assert isinstance(result, list)
    # The prompt explicitly asks that range_query returns real datapoints
    # matching traffic generated in the test environment.
    assert len(result) > 0, "Expected at least one time series for http_requests_total"
    
    # Check that points exist
    points_found = False
    for series in result:
        if len(series.get("values", [])) > 0:
            points_found = True
            break
            
    assert points_found, "Expected values in the returned http_requests_total series"

def test_prometheus_unavailable():
    """
    Test that pointing PROMETHEUS_URL at an unreachable port raises 
    PrometheusUnavailableError.
    """
    original_url = os.environ.get("PROMETHEUS_URL")
    
    try:
        # Point to an unreachable port
        os.environ["PROMETHEUS_URL"] = "http://localhost:9999"
        
        with pytest.raises(PrometheusUnavailableError):
            instant_query("up")
            
    finally:
        # Restore environment
        if original_url is not None:
            os.environ["PROMETHEUS_URL"] = original_url
        else:
            del os.environ["PROMETHEUS_URL"]

def test_loki_query_range_success():
    """
    Test that Loki query_range on {job="simulator"} returns real log entries.
    """
    import requests
    try:
        requests.get(os.environ.get("LOKI_URL", "http://localhost:3100"), timeout=1.0)
    except requests.exceptions.RequestException:
        pytest.skip("Loki not available")
        
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=5)
    
    result = query_range('{job="simulator"}', start, end)
    
    assert isinstance(result, list)
    assert len(result) > 0, 'Expected at least one log line for {job="simulator"}'
    
    # Check shape of returned flattened items
    first_log = result[0]
    assert "timestamp" in first_log
    assert "log_line" in first_log
    assert "labels" in first_log

def test_loki_unavailable():
    """
    Test that pointing LOKI_URL at an unreachable port raises LokiUnavailableError.
    """
    original_url = os.environ.get("LOKI_URL")
    
    try:
        os.environ["LOKI_URL"] = "http://localhost:9999"
        
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=5)
        
        with pytest.raises(LokiUnavailableError):
            query_range('{job="simulator"}', start, end)
            
    finally:
        if original_url is not None:
            os.environ["LOKI_URL"] = original_url
        else:
            del os.environ["LOKI_URL"]
