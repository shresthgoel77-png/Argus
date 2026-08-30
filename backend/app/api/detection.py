from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Incident
from app.detection.engine import get_detection_status, run_detection_pass
from typing import Optional

router = APIRouter()

@router.get("/detection/status")
def detection_status():
    """Report the actual in-memory state of the detection loop."""
    return get_detection_status()

@router.post("/detection/run")
def run_detection(db: Session = Depends(get_db)):
    """Runs a detection pass immediately."""
    new_incidents = run_detection_pass(db, service="simulator")
    # Explicit mapping required because db_session.refresh() marks keys expired
    # which hides them from FastAPI's native jsonable_encoder dictionary scan
    res_list = [
        {c.name: getattr(inc, c.name) for c in inc.__table__.columns}
        for inc in new_incidents
    ]
    return {"new_incidents": res_list}

@router.get("/incidents")
def list_incidents(status: Optional[str] = None, db: Session = Depends(get_db)):
    """Lists incidents, newest first, optional status filter."""
    if status is not None and status not in ("open", "investigating", "investigated", "rca_complete", "remediating", "resolved"):
        raise HTTPException(status_code=400, detail=f"Invalid status filter: {status}")
        
    query = db.query(Incident)
    if status:
        query = query.filter(Incident.status == status)
        
    incidents = query.order_by(Incident.timestamp.desc()).all()
    return incidents

@router.get("/incidents/{incident_id}")
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    """Get single incident."""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident
