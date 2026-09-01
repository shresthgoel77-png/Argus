from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import datetime

from app.db import get_db
from app.models import Incident, Evidence, RemediationAction, VerificationResult
from app.github.report_builder import build_rca_report
from app.github.client import get_github_status, GitHubUnconfiguredError, GitHubAPIError
from app.github.engine import create_incident_issue

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

@router.get("/github/status")
def get_status():
    """
    Returns whether GitHub is configured.
    """
    return get_github_status()

@router.post("/incidents/{id}/github-issue")
def create_issue_endpoint(id: int, db: Session = Depends(get_db)):
    """
    Creates a GitHub issue from the RCA report for this incident.
    """
    try:
        result = create_incident_issue(id, db)
        return result
    except GitHubUnconfiguredError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except GitHubAPIError as e:
        raise HTTPException(status_code=502, detail=str(e))

@router.get("/incidents/{id}/github-issue")
def get_issue_endpoint(id: int, db: Session = Depends(get_db)):
    """
    Gets the created GitHub issue details for this incident, if one exists.
    Returns 404 if the incident doesn't exist, and null if the issue hasn't been created.
    """
    incident = db.query(Incident).filter(Incident.id == id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
        
    issue_evidence = db.query(Evidence).filter(Evidence.incident_id == id, Evidence.category == "github_issue").first()
    if issue_evidence and issue_evidence.content:
        return issue_evidence.content
        
    return None
