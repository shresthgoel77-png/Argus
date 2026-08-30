import os
import requests
from datetime import datetime
from typing import List, Dict, Any

class PrometheusUnavailableError(Exception):
    """Raised when Prometheus is unreachable or returns an error."""
    pass

TIMEOUT_SECONDS = 5

def _execute_query(url: str, params: Dict[str, Any]) -> Any:
    try:
        response = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)
        
        # If response is not 200 OK (e.g. 400 Bad Request if syntax is wrong, or 503 if down)
        # However, Prometheus often returns JSON containing the error message even if status is 4xx.
        data = None
        try:
            data = response.json()
        except Exception:
            pass
            
        if response.status_code != 200:
            error_msg = f"HTTP {response.status_code}"
            if data and data.get("status") == "error" and data.get("error"):
                error_msg = data.get("error")
            raise PrometheusUnavailableError(f"Prometheus query failed: {error_msg}")
            
        if not data:
            raise PrometheusUnavailableError("Received empty response from Prometheus.")
            
        if data.get("status") != "success":
            raise PrometheusUnavailableError(f"Prometheus query error: {data.get('error', 'unknown error')}")
            
        return data.get("data", {}).get("result", [])
        
    except requests.exceptions.RequestException as e:
        raise PrometheusUnavailableError(f"Failed to connect to Prometheus: {e}")

def instant_query(promql: str) -> List[Dict[str, Any]]:
    """
    Executes an instant query against Prometheus.
    Returns the parsed JSON data.result.
    """
    base_url = os.getenv("PROMETHEUS_URL", "http://localhost:9090").rstrip('/')
    url = f"{base_url}/api/v1/query"
    params = {"query": promql}
    return _execute_query(url, params)

def range_query(promql: str, start: datetime, end: datetime, step: str = "15s") -> List[Dict[str, Any]]:
    """
    Executes a range query against Prometheus.
    Returns the parsed JSON data.result.
    """
    base_url = os.getenv("PROMETHEUS_URL", "http://localhost:9090").rstrip('/')
    url = f"{base_url}/api/v1/query_range"
    # Prometheus requires timestamp in seconds
    params = {
        "query": promql,
        "start": start.timestamp(),
        "end": end.timestamp(),
        "step": step
    }
    return _execute_query(url, params)
