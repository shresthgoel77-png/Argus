from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db import get_db
from app.models import RemediationAction, Incident
from app.remediation.engine import (
    propose_remediation, 
    approve_remediation, 
    reject_remediation, 
    execute_remediation,
    RemediationUnsupportedError,
    RemediationExecutionError
)

router = APIRouter(prefix="", tags=["remediation"])

class ApprovePayload(BaseModel):
    approved_by: str
    
class RejectPayload(BaseModel):
    rejected_by: str

@router.post("/remediation/propose/{incident_id}")
def propose(incident_id: int, db: Session = Depends(get_db)):
    return propose_remediation(incident_id, db)
    
@router.post("/remediation/{action_id}/approve")
def approve(action_id: int, payload: ApprovePayload, db: Session = Depends(get_db)):
    return approve_remediation(action_id, payload.approved_by, db)
    
@router.post("/remediation/{action_id}/reject")
def reject(action_id: int, payload: RejectPayload, db: Session = Depends(get_db)):
    return reject_remediation(action_id, payload.rejected_by, db)
    
@router.post("/remediation/{action_id}/execute")
def execute(action_id: int, db: Session = Depends(get_db)):
    try:
        return execute_remediation(action_id, db)
    except RemediationUnsupportedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except RemediationExecutionError as e:
        raise HTTPException(status_code=502, detail=str(e))
    
@router.get("/remediation/{action_id}")
def get_action(action_id: int, db: Session = Depends(get_db)):
    action = db.query(RemediationAction).filter(RemediationAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Remediation action not found")
    return action
    
@router.get("/incidents/{id}/remediation")
def get_incident_remediation(id: int, db: Session = Depends(get_db)):
    # Check if incident exists primarily to return 404 if missing,
    # as per requirements, this is a convenience lookup
    incident = db.query(Incident).filter(Incident.id == id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
        
    action = db.query(RemediationAction).filter(RemediationAction.incident_id == id).first()
    return action
