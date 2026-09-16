from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import object_session

from app.core.config import settings
from app.integrations.github.client import GitHubAppClient
from app.models.bot_interaction import BotInteraction
from app.models.repository import Repository
from app.models.user import User
from app.services import ai_connection_service


@dataclass(frozen=True)
class AuthorizationResult:
    authorized: bool
    owner: User | None = None
    skip_reason: str | None = None

    @property
    def user(self) -> User | None:
        """Compatibility alias for callers that refer to the owning user."""
        return self.owner


def _denied(reason: str) -> AuthorizationResult:
    return AuthorizationResult(authorized=False, skip_reason=reason)


async def authorize_mention(
    repository: Repository, requester_github_login: str
) -> AuthorizationResult:
    """Decide whether a mention may trigger an AI-backed bot response."""
    if not repository.monitoring_enabled:
        return _denied("monitoring_disabled")

    try:
        connection = repository.connection
        owner = connection.user if connection is not None else None
    except Exception:
        owner = None
    if owner is None:
        return _denied("owner_unresolved")

    db = object_session(repository)
    if db is None:
        return _denied("owner_unresolved")

    try:
        connection_status = ai_connection_service.get_connection_status(db, owner.id)
    except Exception:
        return _denied("ai_not_configured")
    if connection_status is None or connection_status.get("status") != "valid":
        return _denied("ai_not_configured")

    try:
        async with GitHubAppClient(connection.installation_id) as client:
            permission = await client.get_collaborator_permission(
                repository.full_name, requester_github_login
            )
    except Exception:
        return _denied("permission_check_failed")

    if isinstance(permission, dict):
        permission = permission.get("permission")
    if permission not in {"write", "maintain", "admin"}:
        return _denied("insufficient_permission")

    trailing_hour = datetime.now(timezone.utc) - timedelta(hours=1)
    try:
        interaction_count = db.query(func.count(BotInteraction.id)).filter(
            BotInteraction.repository_id == repository.id,
            BotInteraction.created_at >= trailing_hour,
        ).scalar()
    except Exception:
        return _denied("rate_limited")
    if interaction_count >= settings.bot_max_interactions_per_hour:
        return _denied("rate_limited")

    return AuthorizationResult(authorized=True, owner=owner)