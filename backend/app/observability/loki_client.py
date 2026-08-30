import os
import requests
from datetime import datetime
from typing import List, Dict, Any

class LokiUnavailableError(Exception):
    """Raised when Loki is unreachable or returns an error."""
    pass

TIMEOUT_SECONDS = 5

def query_range(logql: str, start: datetime, end: datetime, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Executes a range query against Loki and flattens the result into a list of
    {timestamp, log_line, labels} dictionaries.
    """
    base_url = os.getenv("LOKI_URL", "http://localhost:3100").rstrip('/')
    url = f"{base_url}/loki/api/v1/query_range"
    
    # Loki uses nanosecond timestamps for start and end
    # We multiply by 1e9 to convert seconds to nanoseconds
    params = {
        "query": logql,
        "start": str(int(start.timestamp() * 1e9)),
        "end": str(int(end.timestamp() * 1e9)),
        "limit": str(limit)
    }
    
    try:
        response = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)
        
        data = None
        try:
            data = response.json()
        except Exception:
            pass
            
        if response.status_code != 200:
            error_msg = f"HTTP {response.status_code}"
            if data and data.get("status") == "error" and data.get("error"):
                error_msg = data.get("error")
            elif data and isinstance(data, str):
                error_msg = data
            raise LokiUnavailableError(f"Loki query failed: {error_msg}")
            
        if not data:
            raise LokiUnavailableError("Received empty response from Loki.")
            
        if data.get("status") != "success":
            # Sometimes Loki doesn't return a 'status' field when successful, but if it's there and not success...
            # Wait, Loki query_range API actually returns {"status": "success", "data": {...}}
            if "status" in data and data["status"] != "success":
                raise LokiUnavailableError(f"Loki query error: {data.get('error', 'unknown error')}")
        
        results = data.get("data", {}).get("result", [])
        
        flattened = []
        for stream in results:
            # stream could be from 'streams' (matrix/stream type) resultType
            labels = stream.get("stream", {})
            values = stream.get("values", [])
            for value in values:
                if len(value) >= 2:
                    timestamp_ns = value[0]
                    log_line = value[1]
                    flattened.append({
                        "timestamp": timestamp_ns,
                        "log_line": log_line,
                        "labels": labels
                    })
                    
        return flattened
        
    except requests.exceptions.RequestException as e:
        raise LokiUnavailableError(f"Failed to connect to Loki: {e}")
