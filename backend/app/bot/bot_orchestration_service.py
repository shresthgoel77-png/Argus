"""Bot mention orchestration — single entry point for the entire bot flow.

Called from the webhook dispatch layer as a never-propagate side-effect.
Every mention attempt (answered, failed, or skipped) produces exactly one
BotInteraction row, except when no mention is detected at all.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.bot import mention_parser, question_parser
from app.bot.authorization_service import authorize_mention
from app.bot.context_builder import build_bot_context
from app.bot.question_parser import BotIntent
from app.core.logging import get_logger
from app.integrations.ai import get_provider
from app.integrations.github.client import GitHubAppClient
from app.integrations.github.webhook_events import NormalizedWebhookEvent
from app.models.ai_connection import AIConnection
from app.models.bot_interaction import BotInteraction
from app.models.github_event import GitHubEvent
from app.models.repository import Repository
from app.services import ai_connection_service

logger = get_logger(__name__)

_STATIC_HELP_REPLY = (
    "👋 Hi! I can help with the following commands:\n\n"
    "• **CI status** — ask about CI failures, builds, or pipelines\n"
    "• **PR summary** — summarize a pull request (comment on a PR)\n"
    "• **Explain issue** — explain what an issue is about\n"
    "• **Repo attention** — what needs attention in this repository\n\n"
    "Try mentioning me with one of these topics!"
)


def _comment_body(payload: dict) -> str:
    comment = payload.get("comment")
    if isinstance(comment, dict):
        return comment.get("body", "") or ""
    return ""


def _requester_login(payload: dict) -> str | None:
    comment = payload.get("comment")
    if isinstance(comment, dict):
        user = comment.get("user")
        if isinstance(user, dict):
            return user.get("login")
    return None


def _issue_number(payload: dict) -> int | None:
    issue = payload.get("issue")
    if isinstance(issue, dict):
        return issue.get("number")
    return None


def _is_pull_request(payload: dict) -> bool:
    issue = payload.get("issue")
    if isinstance(issue, dict):
        return "pull_request" in issue
    return False


def _sanitize_error(error: Exception) -> str:
    msg = str(error)
    if len(msg) > 500:
        msg = msg[:497] + "..."
    return msg


def _persist_interaction(
    db: Session,
    *,
    repository_id,
    github_event_id,
    requester_github_login: str,
    intent: str,
    question_text: str,
    status: str,
    skip_reason: str | None = None,
    response_text: str | None = None,
    error_message: str | None = None,
    github_reply_comment_id: int | None = None,
    completed_at: datetime | None = None,
) -> BotInteraction:
    interaction = BotInteraction(
        repository_id=repository_id,
        github_event_id=github_event_id,
        requester_github_login=requester_github_login,
        intent=intent,
        question_text=question_text,
        status=status,
        skip_reason=skip_reason,
        response_text=response_text,
        error_message=error_message,
        github_reply_comment_id=github_reply_comment_id,
        completed_at=completed_at,
    )
    db.add(interaction)
    db.commit()
    db.refresh(interaction)
    return interaction


async def handle_mention(
    db: Session,
    github_event: GitHubEvent,
    repository: Repository,
    normalized_event: NormalizedWebhookEvent,
) -> None:
    """Process a potential bot mention from an issue_comment webhook.

    This function is the *sole* entry point for the bot flow.  It is designed
    to be wrapped in a never-propagate try/except at the call site so that a
    failure here can never break the existing analyzer pipeline.
    """
    payload = normalized_event.raw_payload or {}

    # 1. Mention extraction — early exit if no mention
    comment_body = _comment_body(payload)
    question_text = mention_parser.extract_mention(comment_body)
    if question_text is None:
        return  # No mention → no row, no cost

    requester = _requester_login(payload) or "unknown"
    issue_num = _issue_number(payload)
    is_pr = _is_pull_request(payload)

    # 2. Intent classification
    intent = question_parser.classify_intent(question_text, is_pr)

    # 3. Unknown-intent path — static help reply
    if intent == BotIntent.unknown:
        await _handle_unknown_intent(
            db, github_event, repository, normalized_event,
            requester, question_text, issue_num,
        )
        return

    # 4. Authorization (full check — AI connection, permissions, rate limit)
    auth_result = await authorize_mention(repository, requester)

    if not auth_result.authorized:
        # Denied — persist skipped row, no GitHub reply, return silently
        _persist_interaction(
            db,
            repository_id=repository.id,
            github_event_id=github_event.id,
            requester_github_login=requester,
            intent=intent.value,
            question_text=question_text,
            status="skipped",
            skip_reason=auth_result.skip_reason,
        )
        return

    # 5. Persist pending row immediately (observability)
    interaction = _persist_interaction(
        db,
        repository_id=repository.id,
        github_event_id=github_event.id,
        requester_github_login=requester,
        intent=intent.value,
        question_text=question_text,
        status="pending",
    )

    try:
        # 6. Context building
        context = await build_bot_context(intent, repository, normalized_event)
        if context is None:
            raise RuntimeError("Context builder returned None for a known intent")

        # 7. Decrypted API key — used only in-memory for this single call
        api_key = ai_connection_service.get_decrypted_api_key(db, auth_result.owner.id)

        # 8. AI provider call
        ai_conn = (
            db.query(AIConnection)
            .filter_by(user_id=auth_result.owner.id)
            .first()
        )
        if ai_conn is None:
            raise RuntimeError("AI connection not found for authorized user")
        provider_cls = get_provider(ai_conn.provider)
        provider = provider_cls(api_key=api_key)
        result = provider.generate_bot_response(context)
        # api_key goes out of scope here — never stored, never logged

        # 9. Post comment to GitHub
        owner_name, repo_name = repository.full_name.split("/", 1)
        async with GitHubAppClient(repository.connection.installation_id) as client:
            posted = await client.post_issue_comment(
                owner_name, repo_name, issue_num, result.answer_text,
            )

        # 10. Success — update row
        interaction.status = "completed"
        interaction.response_text = result.answer_text
        interaction.github_reply_comment_id = posted.id
        interaction.completed_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as exc:
        # Failure — update row, NO GitHub comment
        db.refresh(interaction)
        interaction.status = "failed"
        interaction.error_message = _sanitize_error(exc)
        interaction.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.error(
            "Bot orchestration inner failure",
            exc_info=True,
            extra={"interaction_id": str(interaction.id)},
        )


async def _handle_unknown_intent(
    db: Session,
    github_event: GitHubEvent,
    repository: Repository,
    normalized_event: NormalizedWebhookEvent,
    requester: str,
    question_text: str,
    issue_num: int | None,
) -> None:
    """Handle unknown-intent mentions with a static help reply.

    Only performs a basic write-permission gate (to avoid replying to
    arbitrary public comments).  Skips AI-connection and rate-limit checks
    because this path never calls the AI provider.
    """
    # Basic permission gate
    try:
        async with GitHubAppClient(repository.connection.installation_id) as client:
            permission = await client.get_collaborator_permission(
                repository.full_name, requester,
            )
    except Exception:
        permission = None

    if isinstance(permission, dict):
        permission = permission.get("permission")

    if permission not in {"write", "maintain", "admin"}:
        _persist_interaction(
            db,
            repository_id=repository.id,
            github_event_id=github_event.id,
            requester_github_login=requester,
            intent="unknown",
            question_text=question_text,
            status="skipped",
            skip_reason="insufficient_permission",
        )
        return

    # Post static help reply
    posted_id: int | None = None
    try:
        owner_name, repo_name = repository.full_name.split("/", 1)
        async with GitHubAppClient(repository.connection.installation_id) as client:
            posted = await client.post_issue_comment(
                owner_name, repo_name, issue_num, _STATIC_HELP_REPLY,
            )
            posted_id = posted.id
    except Exception:
        logger.warning("Failed to post static help reply", exc_info=True)

    _persist_interaction(
        db,
        repository_id=repository.id,
        github_event_id=github_event.id,
        requester_github_login=requester,
        intent="unknown",
        question_text=question_text,
        status="completed",
        response_text=_STATIC_HELP_REPLY,
        github_reply_comment_id=posted_id,
        completed_at=datetime.now(timezone.utc),
    )
