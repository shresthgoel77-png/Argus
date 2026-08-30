from sqlalchemy.orm import Session
from app.models import Incident, Evidence

def build_evidence_package(incident: Incident, db_session: Session) -> dict:
    """
    Fetches all Evidence rows for the incident and returns a single JSON-serializable dict.
    This is a pure, non-lossy transformation of the investigation evidence.
    """
    evidence_rows = db_session.query(Evidence).filter(Evidence.incident_id == incident.id).all()
    
    incident_dict = {
        "id": incident.id,
        "type": incident.type,
        "service": incident.service,
        "severity": incident.severity,
        "timestamp": incident.timestamp.isoformat() if incident.timestamp else None,
        "status": incident.status,
        "initial_metrics": incident.initial_metrics,
        "trigger": incident.trigger
    }
    
    evidence_list = []
    for row in evidence_rows:
        evidence_list.append({
            "id": str(row.id),
            "category": row.category,
            "content": row.content,
            "created_at": row.created_at.isoformat() if row.created_at else None
        })
        
    return {
        "incident": incident_dict,
        "evidence": evidence_list
    }
