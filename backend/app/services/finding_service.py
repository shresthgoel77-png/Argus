import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.finding import Finding
from app.monitoring.analyzer_base import FindingDraft
from app.services import finding_lifecycle_service
from app.services.priority_service import compute_priority

logger = get_logger(__name__)


@dataclass
class SyncResult:
    created: int = 0
    updated: int = 0
    auto_resolved: int = 0
    skipped_ignored: int = 0


def _create_or_update_finding(
    db: Session,
    *,
    repository_id: uuid.UUID,
    category: str,
    type_: str,
    title: str,
    description: str,
    severity: str,
    source: str,
    evidence: dict[str, Any],
    fingerprint: str | None,
) -> tuple[Finding, bool]:
    """Insert a finding, or update the open row when the DB constraint wins."""
    priority = compute_priority(category=category, severity=severity)
    finding = Finding(
        repository_id=repository_id,
        category=category,
        type=type_,
        title=title,
        description=description,
        severity=severity,
        source=source,
        evidence=evidence,
        priority=priority,
        fingerprint=fingerprint,
    )

    if fingerprint is None:
        db.add(finding)
        db.commit()
        db.refresh(finding)
        return finding, True

    try:
        # Deduplication is intentionally delegated to the partial unique index.
        # The savepoint keeps the session usable after an IntegrityError.
        with db.begin_nested():
            db.add(finding)
            db.flush()
        db.commit()
        db.refresh(finding)
        return finding, True
    except IntegrityError:
        existing = (
            db.query(Finding)
            .filter(
                Finding.repository_id == repository_id,
                Finding.fingerprint == fingerprint,
                Finding.status == "open",
            )
            .first()
        )
        if existing is None:
            raise

        existing.title = title
        existing.description = description
        existing.evidence = evidence
        existing.priority = priority
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing, False


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
    evidence: dict[str, Any],
    fingerprint: str | None = None,
) -> Finding:
    """Create a finding, deduplicating fingerprinted open findings."""
    finding, _ = _create_or_update_finding(
        db,
        repository_id=repository_id,
        category=category,
        type_=type_,
        title=title,
        description=description,
        severity=severity,
        source=source,
        evidence=evidence,
        fingerprint=fingerprint,
    )
    return finding


def sync_findings_for_run(
    db: Session,
    *,
    repository_id: uuid.UUID,
    category: str,
    analyzer_key: str,
    drafts: list[FindingDraft],
) -> SyncResult:
    """Synchronize findings reported by a full-state analyzer run."""
    result = SyncResult()
    touched_fingerprints: set[str] = set()
    source = f"on_demand:{analyzer_key}"

    for draft in drafts:
        finding, created = _create_or_update_finding(
            db,
            repository_id=repository_id,
            category=category,
            type_=draft.type_,
            title=draft.title,
            description=draft.description,
            severity=draft.severity,
            source=source,
            evidence=draft.evidence,
            fingerprint=draft.fingerprint,
        )
        if created:
            result.created += 1
        else:
            result.updated += 1
        if finding.fingerprint is not None:
            touched_fingerprints.add(finding.fingerprint)

    missing_filters = [
        Finding.repository_id == repository_id,
        Finding.category == category,
        Finding.fingerprint.is_not(None),
    ]
    if touched_fingerprints:
        missing_filters.append(~Finding.fingerprint.in_(touched_fingerprints))

    missing_open = (
        db.query(Finding)
        .filter(*missing_filters, Finding.status == "open")
        .all()
    )
    for finding in missing_open:
        finding_lifecycle_service.auto_resolve_finding(db, finding)
        result.auto_resolved += 1

    result.skipped_ignored = (
        db.query(Finding)
        .filter(*missing_filters, Finding.status == "ignored")
        .count()
    )
    return result


def list_findings_for_repository(
    db: Session,
    repository_id: uuid.UUID,
    *,
    category: Optional[str] = None,
    limit: int = 50,
) -> list[Finding]:
    """List findings for a repository, optionally filtered by category."""
    query = db.query(Finding).filter(Finding.repository_id == repository_id)
    if category is not None:
        query = query.filter(Finding.category == category)
    return query.order_by(desc(Finding.detected_at)).limit(limit).all()
