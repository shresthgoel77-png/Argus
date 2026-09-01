import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import Incident, Evidence, RemediationAction, VerificationResult
from app.github.client import get_github_status, create_github_issue, GitHubUnconfiguredError, GitHubAPIError
from app.github.report_builder import build_rca_report

def create_incident_issue(incident_id: int, db: Session) -> dict:
    """
    Orchestrates the creation of a GitHub issue from an incident's RCA report.
    Guards:
    1. Incident must exist (caller standard route handles 404 implicitly, but we fetch it).
    2. Incident must have an ai_rca evidence row.
    3. Incident must not already have a github_issue.
    4. GitHub must be configured.
    """
    # 1. Fetch incident
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
        
    # Fetch all evidence
    evidence_rows = db.query(Evidence).filter(Evidence.incident_id == incident_id).all()
    
    # 2. Require ai_rca evidence
    has_rca = any(e.category == "ai_rca" for e in evidence_rows)
    if not has_rca:
        raise HTTPException(status_code=409, detail="RCA required before creating an issue")
        
    # 3. Require no existing github_issue evidence
    has_issue = any(e.category == "github_issue" for e in evidence_rows)
    if has_issue:
        raise HTTPException(status_code=409, detail="GitHub issue already created for this incident")
        
    # 4. Check configuration
    status = get_github_status()
    if not status["configured"]:
        raise GitHubUnconfiguredError("GitHub integration is not correctly configured (check GITHUB_TOKEN and GITHUB_REPO formats).")
        
    # 5. Bring in remediation and verification for the report
    remediation_action = db.query(RemediationAction).filter(RemediationAction.incident_id == incident_id).first()
    verification_result = db.query(VerificationResult).filter(VerificationResult.incident_id == incident_id).first()
    
    report_markdown = build_rca_report(
        incident=incident,
        evidence_rows=evidence_rows,
        remediation_action=remediation_action,
        verification_result=verification_result
    )
    
    # 6. Build title
    id_prefix = str(incident.id)[:8]
    title = f"[AI-RCA] {incident.type} in {incident.service} ({incident.severity}) — {id_prefix}"
    
    # 7. Call client with error handling
    try:
        result = create_github_issue(title, report_markdown)
    except GitHubAPIError as e:
        # On failure, log evidence but DO NOT change incident status
        error_evidence = Evidence(
            incident_id=incident.id,
            category="github_issue_error",
            content={"error": str(e)},
            created_at=datetime.datetime.now(datetime.timezone.utc)
        )
        db.add(error_evidence)
        db.commit()
        raise  # Will be mapped to 502 by the route
        
    # On success, log evidence but DO NOT change incident status
    success_evidence = Evidence(
        incident_id=incident.id,
        category="github_issue",
        content={
            "issue_number": result["issue_number"],
            "issue_url": result["issue_url"],
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        },
        created_at=datetime.datetime.now(datetime.timezone.utc)
    )
    db.add(success_evidence)
    db.commit()
    
    return result
