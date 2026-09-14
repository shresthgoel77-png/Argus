from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.finding import Finding

class InvalidFindingTransition(Exception):
    """Exception raised for invalid state transitions on a Finding."""
    pass

def acknowledge_finding(db: Session, finding: Finding) -> Finding:
    """Valid only from open. Sets status='acknowledged', acknowledged_at=now()."""
    if finding.status != "open":
        raise InvalidFindingTransition(f"Cannot acknowledge finding with status: {finding.status}")
    
    finding.status = "acknowledged"
    finding.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(finding)
    return finding

def resolve_finding(db: Session, finding: Finding, *, source: str = "manual") -> Finding:
    """
    Valid from open or acknowledged. Sets status='resolved', resolved_at=now(), resolution_source=source.
    No-op if already resolved. Raises if ignored.
    """
    if finding.status == "resolved":
        return finding
        
    if finding.status not in ("open", "acknowledged"):
        raise InvalidFindingTransition(f"Cannot resolve finding from status: {finding.status}")
        
    finding.status = "resolved"
    finding.resolved_at = datetime.now(timezone.utc)
    finding.resolution_source = source
    db.commit()
    db.refresh(finding)
    return finding

def ignore_finding(db: Session, finding: Finding) -> Finding:
    """
    Valid from open or acknowledged. Sets status='ignored'.
    No-op if already ignored. Raises if resolved.
    """
    if finding.status == "ignored":
        return finding
        
    if finding.status not in ("open", "acknowledged"):
        raise InvalidFindingTransition(f"Cannot ignore finding from status: {finding.status}")
        
    finding.status = "ignored"
    db.commit()
    db.refresh(finding)
    return finding

def reopen_finding(db: Session, finding: Finding) -> Finding:
    """
    Valid from resolved, ignored, or acknowledged.
    Sets status='open', clears resolved_at, resolution_source, acknowledged_at.
    No-op if already open.
    """
    if finding.status == "open":
        return finding
        
    if finding.status not in ("resolved", "ignored", "acknowledged"):
        raise InvalidFindingTransition(f"Cannot reopen finding from status: {finding.status}")
        
    finding.status = "open"
    finding.resolved_at = None
    finding.resolution_source = None
    finding.acknowledged_at = None
    db.commit()
    db.refresh(finding)
    return finding

def auto_resolve_finding(db: Session, finding: Finding) -> Finding:
    """
    Internal-use only transition.
    behaves like resolve_finding(source="auto"), but silently no-ops if 
    finding is manually ignored or already resolved.
    """
    if finding.status in ("resolved", "ignored"):
        return finding
        
    if finding.status not in ("open", "acknowledged"):
        raise InvalidFindingTransition(f"Cannot auto-resolve finding from status: {finding.status}")
        
    finding.status = "resolved"
    finding.resolved_at = datetime.now(timezone.utc)
    finding.resolution_source = "auto"
    db.commit()
    db.refresh(finding)
    return finding
