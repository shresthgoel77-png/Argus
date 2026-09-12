import uuid
from typing import Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.finding import Finding
from app.core.logging import get_logger

logger = get_logger(__name__)

def create_finding(
    db: Session,
    *,
    repository_id: uuid.UUID,
    category: str,
    type_: str,
    title: str,
    description: str,
    severity: str,
    source: str,
    evidence: dict[str, Any]
) -> Finding:
    """
    Creates a new Finding in the db without deduplication or idempotency checks.
    
    NOTE: Duplicate findings across repeated analyzer runs are an accepted, known 
    limitation in Phase 6 and will be handled by Phase 7's deduplication work.
    Do not attempt ad hoc dedup logic here.
    """
    finding = Finding(
        repository_id=repository_id,
        category=category,
        type=type_,
        title=title,
        description=description,
        severity=severity,
        source=source,
        evidence=evidence
    )
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return finding

def list_findings_for_repository(
    db: Session, 
    repository_id: uuid.UUID, 
    *, 
    category: Optional[str] = None, 
    limit: int = 50
) -> list[Finding]:
    """
    Lists findings for a given repository. This is an internal helper.
    """
    query = db.query(Finding).filter(Finding.repository_id == repository_id)
    
    if category is not None:
         query = query.filter(Finding.category == category)
         
    return query.order_by(desc(Finding.detected_at)).limit(limit).all()
