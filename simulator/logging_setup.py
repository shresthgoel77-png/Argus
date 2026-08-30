import logging
import os
import json
import time
import datetime
import threading
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")
LOKI_URL = os.environ.get("LOKI_URL", "http://localhost:3100")

class JSONFormatter(logging.Formatter):
    def format(self, record):
        # We expect a dict msg, otherwise format as standard string
        message = record.getMessage()
        log_entry = {}
        
        # Construct dict if msg is dict
        if isinstance(record.msg, dict):
            log_entry = dict(record.msg)
        else:
            log_entry = {"message": message}
            
        # Ensure timestamp exists
        if "timestamp" not in log_entry:
            log_entry["timestamp"] = datetime.datetime.fromtimestamp(
                record.created, tz=datetime.timezone.utc
            ).isoformat()
            
        return json.dumps(log_entry)


class LokiHandler(logging.Handler):
    """Best-effort Loki push handler. Never blocks or crashes the app."""
    
    def __init__(self):
        super().__init__()
        self._push_url = f"{LOKI_URL}/loki/api/v1/push"
        # Import requests lazily to avoid import-time issues
        try:
            import requests as _requests
            self._requests = _requests
        except ImportError:
            self._requests = None
    
    def emit(self, record):
        if self._requests is None:
            return
            
        try:
            # Extract labels from the log record
            if isinstance(record.msg, dict):
                log_data = dict(record.msg)
            else:
                log_data = {"message": record.getMessage()}
            
            endpoint = log_data.get("endpoint", "unknown")
            status_code = log_data.get("status_code", 0)
            
            # Categorize status
            if status_code >= 500:
                status_bucket = "5xx"
            elif status_code >= 400:
                status_bucket = "4xx"
            else:
                status_bucket = "2xx"
            
            # Loki push payload
            timestamp_ns = str(int(time.time() * 1e9))
            log_line = json.dumps(log_data)
            
            payload = {
                "streams": [{
                    "stream": {
                        "job": "simulator",
                        "endpoint": endpoint,
                        "status": status_bucket
                    },
                    "values": [
                        [timestamp_ns, log_line]
                    ]
                }]
            }
            
            # Fire-and-forget in a thread to avoid blocking
            def _push():
                try:
                    self._requests.post(
                        self._push_url,
                        json=payload,
                        timeout=1,
                        headers={"Content-Type": "application/json"}
                    )
                except Exception:
                    pass  # Best-effort: swallow silently
            
            t = threading.Thread(target=_push, daemon=True)
            t.start()
            
        except Exception:
            # Never let Loki push break the application
            pass


def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    
    logger = logging.getLogger("simulator")
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Don't pass to uvicorn/fastapi roots
    
    if logger.hasHandlers():
        logger.handlers.clear()
        
    # File handler (existing)
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5)
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)
    
    # Loki handler (best-effort push)
    loki_handler = LokiHandler()
    logger.addHandler(loki_handler)
    
    return logger

logger = setup_logging()
