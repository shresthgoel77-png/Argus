import json
import os
import subprocess
from config import CONFIG_PATH, DEFAULT_CONFIG, get_config
import logging

logger = logging.getLogger("simulator")

BAD_CONFIG = {
    "error_rate": 0.22,
    "latency_ms_base": 1800,
    "latency_ms_jitter": 400,
    "webhook_failure_rate": 0.30
}

def get_state() -> dict:
    cfg = get_config()
    is_bad = (cfg.get("error_rate") != DEFAULT_CONFIG["error_rate"])
    return {
        "bad_deployment_active": is_bad,
        "config": cfg
    }

def _commit_config(message: str) -> str:
    # Explicitly bound to the repo root folder to perform git operations
    cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    try:
        # Set local scope bot identity
        subprocess.run(["git", "config", "user.name", "reliability-sim-bot"], cwd=cwd, check=True)
        subprocess.run(["git", "config", "user.email", "sim-bot@local"], cwd=cwd, check=True)
        
        # Add config file explicit path
        config_rel_path = os.path.relpath(CONFIG_PATH, cwd)
        subprocess.run(["git", "add", config_rel_path], cwd=cwd, check=True)
        
        # Check if actually dirty
        status = subprocess.run(["git", "diff", "--staged", "--quiet"], cwd=cwd)
        if status.returncode == 0:
            logger.warning("Attempted to invoke git commit but no changes were staged. Returning current HEAD.")
            sha_result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True, check=True)
            return sha_result.stdout.strip()
            
        subprocess.run(["git", "commit", "-m", message], cwd=cwd, check=True)
        sha_result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True, check=True)
        return sha_result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Git operation failed: {e}. Returning fallback SHA.")
        return "fallback-sha-for-local-qa"

def trigger_bad_deployment() -> str:
    with open(CONFIG_PATH, "w") as f:
        json.dump(BAD_CONFIG, f)
        
    return _commit_config("chore: tune payment gateway timeout and retry thresholds")

def trigger_reset() -> str:
    with open(CONFIG_PATH, "w") as f:
        json.dump(DEFAULT_CONFIG, f)
        
    return _commit_config("revert: restore stable configuration")
