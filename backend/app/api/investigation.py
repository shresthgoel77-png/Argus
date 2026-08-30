from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.investigation.engine import run_investigation
from app.models import Incident, Evidence


router = APIRouter()


@router.post("/investigation/run/{incident_id}")
def run_incident_investigation(incident_id: int, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    if incident.status in {"investigated", "remediating", "resolved"}:
        raise HTTPException(
            status_code=409,
            detail=f"Incident {incident_id} has already been investigated or progressed further",
        )
    return run_investigation(incident_id, db)


@router.get("/incidents/{incident_id}/evidence")
def get_incident_evidence(incident_id: int, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    # We must explicitly query and convert into dicts to avoid SQLAlchemy expired object issues 
    # since FastAPI sometimes tries to lazy load on disconnected sessions depending on returned object
    evidence_rows = db.query(Evidence).filter(Evidence.incident_id == incident_id).all()
    # Explicit mapping required because db_session might close and expire keys
    res_list = [
        {c.name: getattr(ev, c.name) for c in ev.__table__.columns}
        for ev in evidence_rows
    ]
    return res_list
