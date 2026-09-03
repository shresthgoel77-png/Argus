import datetime
import logging
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import Incident, Evidence, RemediationAction, VerificationResult
from app.github.client import get_github_status, create_github_issue, GitHubUnconfiguredError, GitHubAPIError
from app.github.report_builder import build_rca_report

logger = logging.getLogger(__name__)

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
    logger.info("📤 Creating GitHub issue for incident #%s...", incident_id)
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

    logger.info("✅ GitHub issue #%s created: %s", result["issue_number"], result["issue_url"])
    return result

def auto_create_incident_issue(incident_id: int) -> dict:
    """
    Automatically creates a GitHub issue when an incident is detected natively.
    Bypasses the manual RCA requirement. Should be run in a background thread/task.
    """
    from app.db import SessionLocal
    db = SessionLocal()
    try:
        incident = db.query(Incident).filter(Incident.id == incident_id).first()
        if not incident:
            logger.warning("⚠️ auto_create_incident_issue: incident #%s not found, skipping", incident_id)
            return {}

        status = get_github_status()
        if not status["configured"]:
            logger.info("ℹ️ GitHub not configured — skipping auto-issue for incident #%s", incident_id)
            return {}

        evidence_rows = db.query(Evidence).filter(Evidence.incident_id == incident_id).all()

        report_markdown = build_rca_report(
            incident=incident,
            evidence_rows=evidence_rows,
            remediation_action=None,
            verification_result=None
        )

        id_prefix = str(incident.id)[:8]
        title = f"[AI-RCA] {incident.type} in {incident.service} ({incident.severity}) — {id_prefix}"

        logger.info("📤 Auto-creating GitHub issue for incident #%s...", incident_id)
        try:
            result = create_github_issue(title, report_markdown)
        except GitHubAPIError as e:
            logger.error("❌ GitHub API error for incident #%s: %s", incident_id, e)
            error_evidence = Evidence(
                incident_id=incident.id,
                category="github_issue_error",
                content={"error": str(e)},
                created_at=datetime.datetime.now(datetime.timezone.utc)
            )
            db.add(error_evidence)
            db.commit()
            return {}

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
        logger.info("✅ Auto-created GitHub issue #%s: %s", result["issue_number"], result["issue_url"])
        return result
    except Exception as exc:
        logger.exception("💥 Unexpected error in auto_create_incident_issue for incident #%s: %s", incident_id, exc)
        return {}
    finally:
        db.close()
