from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import datetime

from app.db import get_db
from app.models import Incident, Evidence, RemediationAction, VerificationResult
from app.github.report_builder import build_rca_report

router = APIRouter(tags=["github"])

@router.get("/incidents/{id}/report")
def get_incident_report(id: int, db: Session = Depends(get_db)):
    """
    Generate a full Markdown RCA report for the incident.
    """
    incident = db.query(Incident).filter(Incident.id == id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
        
    evidence_rows = db.query(Evidence).filter(Evidence.incident_id == id).all()
    
    # Check if AI RCA has been run
    has_rca = any(e.category == "ai_rca" for e in evidence_rows)
    if not has_rca:
        raise HTTPException(
            status_code=409, 
            detail="Report requires RCA to be completed first"
        )
        
    remediation_action = db.query(RemediationAction).filter(RemediationAction.incident_id == id).first()
    verification_result = db.query(VerificationResult).filter(VerificationResult.incident_id == id).first()
    
    markdown_report = build_rca_report(
        incident=incident,
        evidence_rows=evidence_rows,
        remediation_action=remediation_action,
        verification_result=verification_result
    )
    
    return {
        "markdown": markdown_report,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
