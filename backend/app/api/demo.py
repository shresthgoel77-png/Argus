# REHEARSAL/DEV UTILITY
# This entire router is strictly separated from the golden-path product surface.
# It exists purely to enable repeatable live demonstrations.
import os
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Incident, Evidence, RemediationAction, VerificationResult
from app.detection.engine import detection_status

router = APIRouter(prefix="/demo", tags=["demo"])

@router.post("/reset-data")
async def reset_demo_data(db: Session = Depends(get_db)):
    if os.getenv("DEMO_MODE", "").lower() != "true":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reset unavailable \u2014 set DEMO_MODE=true to enable"
        )
        
    tables_cleared = []
    
    # FK-safe order: verification_results, remediation_actions, evidence, incidents
    db.query(VerificationResult).delete()
    tables_cleared.append("verification_results")
    
    db.query(RemediationAction).delete()
    tables_cleared.append("remediation_actions")
    
    db.query(Evidence).delete()
    tables_cleared.append("evidence")
    
    db.query(Incident).delete()
    tables_cleared.append("incidents")
    
    db.commit()
    
    # Phase 6 detection engine reset
    detection_status.last_run_at = None
    detection_status.last_run_new_incidents = 0
    detection_status.last_error = None
    # Phase 3 in-memory cooldown state - actually, cooldown checks the DB directly,
    # so deleting the incidents table intrinsically clears the cooldown.
    
    # Call simulator reset to guarantee clean baseline
    simulator_url = os.getenv("SIMULATOR_URL", "http://127.0.0.1:8001")
    try:
        async with httpx.AsyncClient() as client:
            await client.post(f"{simulator_url}/simulate/reset", timeout=5.0)
    except Exception as e:
        # We swallow or just log the error since this is a local utility
        pass
        
    return {"status": "reset", "tables_cleared": tables_cleared}
