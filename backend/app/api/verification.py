from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Incident, VerificationResult
from app.verification.engine import run_verification, VerificationStateError

router = APIRouter(prefix="", tags=["verification"])


@router.post("/verification/run/{incident_id}")
def run_verification_endpoint(incident_id: int, db: Session = Depends(get_db)):
    """
    Run verification for a remediated incident.
    
    This is a synchronous, blocking call that may take up to VERIFICATION_MAX_WAIT_SECONDS
    (default 60s) to complete. This is an intentional simplicity tradeoff per §34 of the
    requirements — no background job queue is implemented for this scope.
    
    The caller should be aware that this endpoint will not return immediately; in a production
    system with tighter SLAs, this would be converted to an async job queue pattern.
    
    Status codes:
    - 404: incident not found
    - 409: incident not in "remediated" status, or verification already exists for this incident
    - 200: verification completed (check 'recovered' field to determine pass/fail)
    """
    # Check if incident exists
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    # Check if incident is in remediated status
    if incident.status != "remediated":
        raise HTTPException(
            status_code=409,
            detail=f"Incident must be remediated before verification; current status: {incident.status}"
        )
    
    # Check if verification already exists
    existing_result = (
        db.query(VerificationResult)
        .filter(VerificationResult.incident_id == incident_id)
        .first()
    )
    if existing_result:
        raise HTTPException(
            status_code=409,
            detail="Verification has already been performed for this incident"
        )
    
    # Run the actual verification (blocking call)
    try:
        result = run_verification(incident_id, db)
        return result
    except VerificationStateError as e:
        # This should be rare given the checks above, but handle gracefully
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/incidents/{id}/verification")
def get_incident_verification(id: int, db: Session = Depends(get_db)):
    """
    Get the verification result for an incident.
    
    Returns the VerificationResult if one exists, or null if not yet run.
    This endpoint is designed to support page reloads and polling — a client
    can call this to check if a verification has completed.
    
    Returns 404 only if the incident itself doesn't exist.
    """
    # Check if incident exists (return 404 only if incident missing)
    incident = db.query(Incident).filter(Incident.id == id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    # Get verification result if it exists
    result = db.query(VerificationResult).filter(VerificationResult.incident_id == id).first()
    return result
