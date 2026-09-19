from dataclasses import dataclass
import uuid
from sqlalchemy import case, desc
from sqlalchemy.orm import Session

from app.models.finding import Finding
from app.models.repository_health_snapshot import RepositoryHealthSnapshot


@dataclass
class NeedsAttentionDTO:
    findings: list[Finding]
    health_snapshot: RepositoryHealthSnapshot | None
    reasons: list[str]


def get_needs_attention(db: Session, repository_id: uuid.UUID, limit: int = 5) -> NeedsAttentionDTO:
    """
    Get top open findings ordered by severity, then priority, then detected_at.
    Includes the latest repository health snapshot and its reasons.
    """
    severity_order = case((Finding.severity == "critical", 0), (Finding.severity == "high", 1), else_=2)
    priority_order = case(
        (Finding.priority == "critical", 0),
        (Finding.priority == "high", 1),
        (Finding.priority == "medium", 2),
        (Finding.priority == "low", 3),
        else_=4
    )
    findings = db.query(Finding).filter(
        Finding.repository_id == repository_id,
        Finding.status == "open",
        Finding.severity.in_(("critical", "high")),
    ).order_by(severity_order, priority_order, desc(Finding.detected_at)).limit(limit).all()

    snapshot = db.query(RepositoryHealthSnapshot).filter(
        RepositoryHealthSnapshot.repository_id == repository_id
    ).order_by(desc(RepositoryHealthSnapshot.computed_at)).first()

    reasons = snapshot.reasons if snapshot is not None else []

    return NeedsAttentionDTO(
        findings=findings,
        health_snapshot=snapshot,
        reasons=reasons
    )
