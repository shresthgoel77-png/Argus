import uuid
import logging
import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import Incident, RemediationAction, Evidence
from app.ai.schema import ALLOWED_REMEDIATION_TYPES
from app.remediation.policy import validate_params, PolicyViolationError, REMEDIATION_POLICY
from app.remediation.handlers import ACTION_HANDLERS

class RemediationUnsupportedError(Exception):
    pass

class RemediationExecutionError(Exception):
    pass

logger = logging.getLogger(__name__)

def propose_remediation(incident_id: int, db: Session):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    if incident.status != "rca_complete":
        raise HTTPException(status_code=409, detail="Must complete RCA before proposing remediation")
        
    existing_action = db.query(RemediationAction).filter(RemediationAction.incident_id == incident_id).first()
    if existing_action:
        raise HTTPException(status_code=409, detail="Remediation already proposed for this incident")
        
    evidence_row = db.query(Evidence).filter(
        Evidence.incident_id == incident_id,
        Evidence.category == "ai_rca"
    ).order_by(Evidence.created_at.desc()).first()
    
    if not evidence_row:
        raise Exception("RCA evidence missing despite status='rca_complete'")
        
    rca_content = evidence_row.content
    if not isinstance(rca_content, dict):
        raise Exception("RCA evidence content is not a valid JSON dictionary")
        
    recommended = rca_content.get("recommended_remediation", {})
    action_type = recommended.get("action_type")
    params = recommended.get("params", {})
    
    if action_type not in ALLOWED_REMEDIATION_TYPES:
        raise HTTPException(status_code=400, detail="Invalid action type recommended by AI")
        
    try:
        validate_params(action_type, params)
    except PolicyViolationError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    action = RemediationAction(
        incident_id=incident_id,
        action_type=action_type,
        params=params,
        risk_level=REMEDIATION_POLICY[action_type]["risk_level"],
        approved=False,
        approved_by=None,
        executed_at=None,
        status="pending_approval",
        result=None
    )
    
    db.add(action)
    incident.status = "remediation_proposed"
    db.commit()
    db.refresh(action)
    return action

def approve_remediation(action_id: int, approved_by: str, db: Session):
    action = db.query(RemediationAction).filter(RemediationAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Remediation action not found")
        
    if action.status != "pending_approval":
        raise HTTPException(status_code=409, detail="Remediation action is not pending approval")
        
    if not approved_by or not approved_by.strip():
        raise HTTPException(status_code=400, detail="approved_by cannot be empty")
        
    # In a real system, we would authenticate this identity.
    # Deferred for this build per minimum-viable-security scope constraints.
    action.approved = True
    action.approved_by = approved_by
    action.status = "approved"
    
    db.commit()
    db.refresh(action)
    
    logger.info(f"remediation approved: action_id={action.id}, incident_id={action.incident_id}, approved_by={approved_by}, action_type={action.action_type}")
    
    return action

def reject_remediation(action_id: int, rejected_by: str, db: Session):
    action = db.query(RemediationAction).filter(RemediationAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Remediation action not found")
        
    if action.status != "pending_approval":
        raise HTTPException(status_code=409, detail="Remediation action is not pending approval")
        
    if not rejected_by or not rejected_by.strip():
        raise HTTPException(status_code=400, detail="rejected_by cannot be empty")
        
    action.status = "rejected"
    
    incident = db.query(Incident).filter(Incident.id == action.incident_id).first()
    if incident:
        incident.status = "remediation_rejected"
        
    db.commit()
    db.refresh(action)
    
    logger.info(f"remediation rejected: action_id={action.id}, incident_id={action.incident_id}, rejected_by={rejected_by}, action_type={action.action_type}")
    
    return action

def execute_remediation(action_id: int, db: Session):
    action = db.query(RemediationAction).filter(RemediationAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Remediation action not found")
        
    if action.status != "approved":
        raise HTTPException(status_code=409, detail="Remediation action must be approved before execution")
        
    if action.action_type not in ALLOWED_REMEDIATION_TYPES:
        raise HTTPException(status_code=400, detail="Invalid action type")
        
    handler = ACTION_HANDLERS.get(action.action_type)
    if not handler:
        action.status = "execution_unsupported"
        db.commit()
        raise RemediationUnsupportedError(f"action_type '{action.action_type}' has no execution handler in this build")
        
    incident = db.query(Incident).filter(Incident.id == action.incident_id).first()
    if incident:
        incident.status = "remediating"
        db.commit()
        
    result = handler(action)
    
    if result.get("success"):
        action.status = "executed"
        action.executed_at = datetime.datetime.utcnow()
        action.result = result
        if incident:
            incident.status = "remediated"
        db.commit()
        logger.info(f"Remediation executed successfully: action_id={action.id}, incident_id={action.incident_id}, action_type={action.action_type}, result={result}")
    else:
        action.status = "execution_failed"
        action.result = result
        # incident status stays "remediating"
        db.commit()
        logger.warning(f"Remediation execution failed: action_id={action.id}, incident_id={action.incident_id}, action_type={action.action_type}, error={result.get('error')}")
        raise RemediationExecutionError(result.get("error", "Execution failed"))
        
    return {"action": action, "result": result}
