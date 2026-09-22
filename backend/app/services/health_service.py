import uuid
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.logging import get_logger
from app.core.config import settings
from app.models.repository_health_snapshot import RepositoryHealthSnapshot
from app.models.finding import Finding
from app.models.repository import Repository
from app.models.github_connection import GitHubConnection
from app.services.finding_service import get_all_open_findings_for_repository
from app.services import notification_dispatch_service
from app.services.health_score_service import (
    compute_category_scores,
    compute_overall_score,
    FINDING_CATEGORY_TO_HEALTH_CATEGORY,
)

logger = get_logger(__name__)

def get_latest_snapshot(db: Session, repository_id: uuid.UUID) -> Optional[RepositoryHealthSnapshot]:
    """Retrieve the most recent health snapshot for a repository."""
    return (
        db.query(RepositoryHealthSnapshot)
        .filter(RepositoryHealthSnapshot.repository_id == repository_id)
        .order_by(desc(RepositoryHealthSnapshot.computed_at))
        .first()
    )


def generate_reasons(
    previous: Optional[RepositoryHealthSnapshot],
    category_scores: dict[str, int],
    overall_score: int,
    open_findings: list[Finding],
) -> list[str]:
    """
    Generate deterministic reasons explaining the health score state or delta.
    """
    if previous is None:
        return ["Initial health score computed."]

    deltas = []
    for cat, new_score in category_scores.items():
        old_score = previous.category_scores.get(cat, 100)
        delta = new_score - old_score
        if delta != 0:
            deltas.append((cat, delta))

    if not deltas:
        return ["No change since last check."]

    # Sort descending by magnitude of change, then alphabetically by category for determinism
    deltas.sort(key=lambda x: (-abs(x[1]), x[0]))

    reasons = []

    for cat, delta in deltas:
        if len(reasons) >= 5:
            break

        if delta > 0:
            reasons.append(f"{cat.replace('_', ' ').title()} score improved by {delta} points.")
        else:
            # Drop reason
            examples = []
            seen_types = set()
            for finding in open_findings:
                if FINDING_CATEGORY_TO_HEALTH_CATEGORY.get(finding.category) == cat:
                    type_str = f"[{finding.severity}] {finding.type}"
                    if type_str not in seen_types:
                        seen_types.add(type_str)
                        examples.append(type_str)
                        if len(examples) == 2:
                            break

            base_reason = f"{cat.replace('_', ' ').title()} score dropped by {abs(delta)} points."
            if examples:
                examples_str = ", ".join(examples)
                base_reason += f" Examples: {examples_str}."
            reasons.append(base_reason)

    return reasons


def compute_and_persist_health(db: Session, repository_id: uuid.UUID) -> RepositoryHealthSnapshot:
    """
    Computes health scores based on all open findings, compares with previous snapshot
    to generate reasons, and persists a new snapshot.
    """
    open_findings = get_all_open_findings_for_repository(db, repository_id)

    category_scores = compute_category_scores(open_findings)
    overall_score = compute_overall_score(category_scores)

    previous = get_latest_snapshot(db, repository_id)

    reasons = generate_reasons(previous, category_scores, overall_score, open_findings)

    snapshot = RepositoryHealthSnapshot(
        repository_id=repository_id,
        overall_score=overall_score,
        category_scores=category_scores,
        reasons=reasons,
    )

    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    if previous is not None:
        drop = previous.overall_score - snapshot.overall_score
        if drop >= settings.health_drop_notification_threshold:
            try:
                repo = db.query(Repository).filter(Repository.id == repository_id).first()
                if repo:
                    conn = db.query(GitHubConnection).filter(
                        GitHubConnection.id == repo.connection_id
                    ).first()
                    if conn:
                        severity = (
                            "high"
                            if drop >= 2 * settings.health_drop_notification_threshold
                            else "medium"
                        )
                        message = "\n".join(snapshot.reasons) if snapshot.reasons else "Health score dropped."
                        notification_dispatch_service.dispatch_notification(
                            db,
                            user_id=conn.user_id,
                            repository_id=repository_id,
                            notification_type="health_score_dropped",
                            severity=severity,
                            title="Health Score Dropped",
                            message=message,
                            reference_type="health_snapshot",
                            reference_id=str(snapshot.id),
                        )
            except Exception:
                logger.warning(
                    "Failed to dispatch health score drop notification",
                    exc_info=True,
                    extra={"repository_id": str(repository_id), "snapshot_id": str(snapshot.id)},
                )

    return snapshot
