from typing import Literal, List, Dict, Any
from pydantic import BaseModel

ALLOWED_REMEDIATION_TYPES = [
    "rollback_deployment",
    "restart_service",
    "restart_container"
]

class RemediationRecommendation(BaseModel):
    action_type: str
    params: Dict[str, Any]
    rationale: str

class RCAOutput(BaseModel):
    summary: str
    impact: str
    affected_components: List[str]
    root_cause: str
    confidence: Literal["low", "medium", "high"]
    supporting_evidence: List[str]
    alternative_hypotheses: List[str]
    recommended_fix: str
    recommended_remediation: RemediationRecommendation
