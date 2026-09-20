import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, asc

from app.models.repository_health_snapshot import RepositoryHealthSnapshot
from app.models.finding import Finding
from app.services.health_score_service import HEALTH_CATEGORIES, FINDING_CATEGORY_TO_HEALTH_CATEGORY

def get_health_trend(db: Session, repository_id: uuid.UUID, window_days: int = 30) -> tuple[int, dict[str, int]]:
    """
    Computes overall_delta and per-category deltas for the given window_days.
    Returns: (overall_delta, {category: delta})
    """
    cutoff_date = datetime.utcnow() - timedelta(days=window_days)

    snapshots = (
        db.query(RepositoryHealthSnapshot)
        .filter(
            RepositoryHealthSnapshot.repository_id == repository_id,
            RepositoryHealthSnapshot.computed_at >= cutoff_date
        )
        .order_by(asc(RepositoryHealthSnapshot.computed_at))
        .all()
    )

    category_deltas = {cat: 0 for cat in HEALTH_CATEGORIES}
    if not snapshots or len(snapshots) < 2:
        return 0, category_deltas

    oldest = snapshots[0]
    newest = snapshots[-1]

    overall_delta = newest.overall_score - oldest.overall_score
    for cat in HEALTH_CATEGORIES:
        old_val = oldest.category_scores.get(cat, 100)
        new_val = newest.category_scores.get(cat, 100)
        category_deltas[cat] = new_val - old_val

    return overall_delta, category_deltas

def get_finding_velocity(db: Session, repository_id: uuid.UUID, window_days: int = 30) -> dict[str, dict[str, int]]:
    """
    Counts detected vs resolved findings grouped by category in the given window.
    Returns: { category: {"detected": count, "resolved": count} }
    """
    cutoff_date = datetime.utcnow() - timedelta(days=window_days)

    result = {cat: {"detected": 0, "resolved": 0} for cat in HEALTH_CATEGORIES}

    # Count detections in the window
    detected_counts = (
        db.query(Finding.category, func.count(Finding.id))
        .filter(
            Finding.repository_id == repository_id,
            Finding.detected_at >= cutoff_date
        )
        .group_by(Finding.category)
        .all()
    )
    for category, count in detected_counts:
        health_cat = FINDING_CATEGORY_TO_HEALTH_CATEGORY.get(category)
        if health_cat in result:
            result[health_cat]["detected"] += count

    # Count resolutions in the window
    resolved_counts = (
        db.query(Finding.category, func.count(Finding.id))
        .filter(
            Finding.repository_id == repository_id,
            Finding.resolved_at >= cutoff_date
        )
        .group_by(Finding.category)
        .all()
    )
    for category, count in resolved_counts:
        health_cat = FINDING_CATEGORY_TO_HEALTH_CATEGORY.get(category)
        if health_cat in result:
            result[health_cat]["resolved"] += count

    return result
