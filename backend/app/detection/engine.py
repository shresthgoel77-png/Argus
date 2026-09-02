import datetime
import logging
import os
from dataclasses import asdict, dataclass
from sqlalchemy.orm import Session
from app.models import Incident
from app.detection import detectors
from app.detection.cooldown import should_cool_down
from app.github.engine import auto_create_incident_issue
import threading

logger = logging.getLogger(__name__)


@dataclass
class DetectionStatus:
    """In-memory record of the most recent real detection pass."""

    last_run_at: datetime.datetime | None = None
    last_run_new_incidents: int = 0
    last_error: str | None = None
    poll_interval_seconds: int = int(os.getenv("DETECTION_POLL_INTERVAL_SECONDS", "10"))


detection_status = DetectionStatus()


def get_detection_status() -> dict:
    """Return a serializable snapshot without exposing mutable module state."""
    return asdict(detection_status)

def run_detection_pass(db_session: Session, service: str = "simulator") -> list[Incident]:
    new_incidents = []
    detection_status.poll_interval_seconds = int(os.getenv("DETECTION_POLL_INTERVAL_SECONDS", "10"))
    detection_status.last_run_at = datetime.datetime.now(datetime.UTC)
    detection_status.last_error = None
    
    try:
        results = [
            detectors.detect_high_error_rate(service),
            detectors.detect_high_latency(service),
            detectors.detect_webhook_failure(service),
            detectors.detect_razorpay_tampering(service)
        ]
    except Exception as e:
        logger.error(f"Error querying Prometheus during detection pass: {e}")
        detection_status.last_error = str(e)
        detection_status.last_run_new_incidents = 0
        return []
    
    for res in results:
        if not res.get("firing"):
            continue
            
        detector_type = res.get("type")
        detector_severity = res.get("severity")
        
        # Deduplication check
        existing_open = (
            db_session.query(Incident)
            .filter(
                Incident.service == service,
                Incident.type == detector_type,
                Incident.status.in_(["open", "investigating"])
            )
            .first()
        )
        
        if existing_open:
            logger.debug(f"duplicate suppressed for {service}/{detector_type}")
            continue
            
        # Cooldown check
        if should_cool_down(db_session, service, detector_type):
            logger.debug(f"cooldown suppressed for {service}/{detector_type}")
            continue
            
        # Create incident
        new_incident = Incident(
            type=detector_type,
            service=service,
            severity=detector_severity,
            timestamp=datetime.datetime.utcnow(),
            trigger=f"{detector_type}_threshold_exceeded",
            status="open",
            initial_metrics=res
        )
        db_session.add(new_incident)
        # Flush to prevent another detector in the same pass from creating duplicates
        # It's an integer autoincrement ID, so it will be assigned.
        db_session.commit()
        db_session.refresh(new_incident)
        new_incidents.append(new_incident)
        
        # Fire off issue creation in a background thread so we don't block the polling engine
        threading.Thread(target=auto_create_incident_issue, args=(new_incident.id,)).start()
        
    detection_status.last_run_new_incidents = len(new_incidents)
    return new_incidents
