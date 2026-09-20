from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.bot_interaction import BotInteraction
from app.models.finding import Finding
from app.models.github_event import GitHubEvent
from app.models.repository_health_snapshot import RepositoryHealthSnapshot
from app.schemas.activity import ActivityItem, ActivitySource


def _item(
    source: ActivitySource,
    timestamp: datetime,
    title: str,
    summary: str,
    reference_id: uuid.UUID,
    details: dict | None = None,
) -> ActivityItem:
    return ActivityItem(
        source=source,
        timestamp=timestamp,
        title=title,
        summary=summary[:500],
        reference_id=reference_id,
        details=details,
    )


def get_activity_feed(
    db: Session,
    repository_id: uuid.UUID,
    before: datetime | None = None,
    limit: int = 25,
    source: ActivitySource | None = None,
) -> tuple[list[ActivityItem], datetime | None]:
    """Merge bounded projections from repository history into one page."""
    limit = max(1, min(limit, 100))
    items: list[ActivityItem] = []

    if source in (None, ActivitySource.github_event):
        query = db.query(
            GitHubEvent.id,
            GitHubEvent.event_type,
            GitHubEvent.action,
            GitHubEvent.received_at,
        ).filter(GitHubEvent.repository_id == repository_id)
        if before is not None:
            query = query.filter(GitHubEvent.received_at < before)
        for event_id, event_type, action, received_at in query.order_by(
            desc(GitHubEvent.received_at), desc(GitHubEvent.id)
        ).limit(limit).all():
            items.append(_item(ActivitySource.github_event, received_at, f"{event_type} event", action or "GitHub event received", event_id))

    if source in (None, ActivitySource.finding_detected):
        query = db.query(Finding.id, Finding.title, Finding.severity, Finding.detected_at).filter(
            Finding.repository_id == repository_id,
            Finding.detected_at.is_not(None),
        )
        if before is not None:
            query = query.filter(Finding.detected_at < before)
        for finding_id, title, severity, detected_at in query.order_by(
            desc(Finding.detected_at), desc(Finding.id)
        ).limit(limit).all():
            items.append(_item(ActivitySource.finding_detected, detected_at, title, f"{severity} finding detected", finding_id))

    if source in (None, ActivitySource.finding_resolved):
        query = db.query(Finding.id, Finding.title, Finding.severity, Finding.resolved_at).filter(
            Finding.repository_id == repository_id,
            Finding.resolved_at.is_not(None),
        )
        if before is not None:
            query = query.filter(Finding.resolved_at < before)
        for finding_id, title, severity, resolved_at in query.order_by(
            desc(Finding.resolved_at), desc(Finding.id)
        ).limit(limit).all():
            items.append(_item(ActivitySource.finding_resolved, resolved_at, title, f"{severity} finding resolved", finding_id))

    if source in (None, ActivitySource.health_changed):
        query = db.query(
            RepositoryHealthSnapshot.id,
            RepositoryHealthSnapshot.overall_score,
            RepositoryHealthSnapshot.computed_at,
        ).filter(RepositoryHealthSnapshot.repository_id == repository_id)
        if before is not None:
            query = query.filter(RepositoryHealthSnapshot.computed_at < before)
        for snapshot_id, overall_score, computed_at in query.order_by(desc(RepositoryHealthSnapshot.computed_at), desc(RepositoryHealthSnapshot.id)).limit(limit).all():
            items.append(_item(ActivitySource.health_changed, computed_at, "Repository health changed", f"Overall score: {overall_score}", snapshot_id))

    if source in (None, ActivitySource.bot_interaction):
        query = db.query(
            BotInteraction.id,
            BotInteraction.intent,
            BotInteraction.question_text,
            BotInteraction.status,
            BotInteraction.created_at,
            BotInteraction.skip_reason,
            BotInteraction.response_text,
            BotInteraction.requester_github_login,
        ).filter(BotInteraction.repository_id == repository_id)
        if before is not None:
            query = query.filter(BotInteraction.created_at < before)
        for interaction_id, intent, question_text, status, created_at, skip_reason, response_text, requester_github_login in query.order_by(desc(BotInteraction.created_at), desc(BotInteraction.id)).limit(limit).all():
            details = {
                "intent": intent,
                "status": status,
                "skip_reason": skip_reason,
                "response_text": response_text if status == "completed" else None,
                "requester_github_login": requester_github_login,
                "question_text": question_text,
            }
            items.append(_item(ActivitySource.bot_interaction, created_at, f"Bot interaction: {intent}", f"{status}: {question_text}", interaction_id, details=details))

    items.sort(key=lambda item: (item.timestamp, str(item.reference_id)), reverse=True)
    page = items[:limit]
    return page, page[-1].timestamp if page else None