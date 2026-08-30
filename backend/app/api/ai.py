from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.ai.engine import (
    AIServiceError,
    IncidentNotFoundError,
    RCAStateError,
    run_rca,
)

router = APIRouter()


@router.post("/ai/rca/{incident_id}")
def run_rca_endpoint(incident_id: int, db: Session = Depends(get_db)):
    """
    Run AI-driven Root Cause Analysis for an investigated incident.

    Returns 200 with {incident_id, rca, evidence_id} on success.
    Returns 404 if the incident does not exist.
    Returns 409 if the incident is not yet investigated or RCA already ran.
    Returns 502 if the AI call or validation failed after retry.
    """
    try:
        result = run_rca(incident_id, db)
    except IncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RCAStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except AIServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return result
