import os
import datetime
from sqlalchemy.orm import Session
from app.models import Incident

COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "60"))

def should_cool_down(db: Session, service: str, type: str) -> bool:
    """Returns True if a recent incident for this service and type was resolved within the cooldown period."""
    recent_incident = (
        db.query(Incident)
        .filter(Incident.service == service, Incident.type == type, Incident.status == "resolved")
        .order_by(Incident.resolved_at.desc())
        .first()
    )
    if not recent_incident or not recent_incident.resolved_at:
        return False
    
    time_since_resolution = datetime.datetime.utcnow() - recent_incident.resolved_at
    return time_since_resolution.total_seconds() < COOLDOWN_SECONDS
