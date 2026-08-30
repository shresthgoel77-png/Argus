import os
import httpx
import logging
from typing import Callable, Dict, Any
from app.models import RemediationAction

logger = logging.getLogger(__name__)

def handle_rollback_deployment(action: RemediationAction) -> Dict[str, Any]:
    """
    Executes a rollback operation by calling the simulator's /simulate/reset endpoint.
    """
    simulator_url = os.getenv("SIMULATOR_URL", "http://localhost:9000").rstrip("/")
    url = f"{simulator_url}/simulate/reset"
    
    try:
        # short timeout (e.g. 5s) for the mock simulator
        response = httpx.post(url, timeout=5.0)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "commit_sha": data.get("commit_sha"),
                "simulator_response": data
            }
        else:
            # Non-200 responses are failures
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text}"
            }
    except Exception as e:
        # Connection failures, timeouts, etc.
        logger.warning(f"Connection failure during rollback execution: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# Only map rollback_deployment. 
# Do NOT add restart_service or restart_container.
# This causes the honest 501 for unhandled actions.
ACTION_HANDLERS: Dict[str, Callable[[RemediationAction], Dict[str, Any]]] = {
    "rollback_deployment": handle_rollback_deployment
}
