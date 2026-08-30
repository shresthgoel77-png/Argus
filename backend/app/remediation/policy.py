from app.ai.schema import ALLOWED_REMEDIATION_TYPES

class PolicyViolationError(Exception):
    pass

# A deliberate hackathon-scope simplification:
# a real system might auto-approve "low" risk actions, this one never does.
# All entries require human approval unconditionally.
REMEDIATION_POLICY = {
    "rollback_deployment": {
        "risk_level": "medium",
        "allowed_param_keys": [],
        "verification_method": "metrics_recovery"
    },
    "restart_service": {
        "risk_level": "medium",
        "allowed_param_keys": [],
        "verification_method": "health_check"
    },
    "restart_container": {
        "risk_level": "low",
        "allowed_param_keys": [],
        "verification_method": "health_check"
    },
}

def validate_params(action_type: str, params: dict):
    """
    Validates that the parameters recommended by the AI are allowed
    by the strict policy for that action_type.
    """
    if action_type not in REMEDIATION_POLICY:
        raise PolicyViolationError(f"Unknown action_type: {action_type}")
    
    policy = REMEDIATION_POLICY[action_type]
    allowed_keys = set(policy["allowed_param_keys"])
    
    if not isinstance(params, dict):
        raise PolicyViolationError("params must be a dictionary")
        
    for key in params.keys():
        if key not in allowed_keys:
            raise PolicyViolationError(f"Parameter '{key}' is not allowed for action '{action_type}'")
