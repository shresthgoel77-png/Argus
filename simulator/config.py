import json
import os
import logging

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
DEFAULT_CONFIG = {
    "error_rate": 0.0,
    "latency_ms_base": 50,
    "latency_ms_jitter": 20,
    "webhook_failure_rate": 0.0
}

logger = logging.getLogger("simulator")

# In-memory fallback
_last_good_config = DEFAULT_CONFIG.copy()

def get_config() -> dict:
    """Read the config fresh on every request with fallback mechanism."""
    global _last_good_config
    if not os.path.exists(CONFIG_PATH):
        logger.warning(f"config.json missing at {CONFIG_PATH}, using fallback defaults.")
        return DEFAULT_CONFIG.copy()
        
    try:
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f)
            # Ensure expected fields exist
            for k in DEFAULT_CONFIG.keys():
                if k not in data:
                    data[k] = DEFAULT_CONFIG[k]
                    
            _last_good_config = data.copy()
            return data
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Failed to read config.json (maybe mid-write?): {e}. Using last known good values.")
        return _last_good_config.copy()
