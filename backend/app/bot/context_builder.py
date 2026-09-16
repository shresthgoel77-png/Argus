from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import case, desc
from sqlalchemy.orm import object_session

from app.bot.question_parser import BotIntent
from app.integrations.github.client import GitHubAppClient
from app.integrations.github.webhook_events import NormalizedWebhookEvent
from app.models.finding import Finding
from app.models.repository import Repository
from app.models.repository_health_snapshot import RepositoryHealthSnapshot
from app.services.ai_context_common import (
    SYSTEM_INSTRUCTIONS_BLOCK,
    extract_untrusted_content,
    truncate,
    wrap_untrusted_content,
)


@dataclass(frozen=True)
class BotContext:
    intent: BotIntent
    system_instructions: str
    untrusted_content: str
    source: str
    static_response: str | None = None


def _payload(event: NormalizedWebhookEvent) -> dict[str, Any]:
    return event.raw_payload if isinstance(event.raw_payload, dict) else {}


def _resource_number(event: NormalizedWebhookEvent, key: str) -> int | None:
    value = _payload(event).get(key, {})
    if key == "pull_request" and not isinstance(value, dict):
        value = _payload(event).get("issue", {})
    elif key == "pull_request" and isinstance(value, dict) and value.get("number") is None:
        value = _payload(event).get("issue", value)
    if not isinstance(value, dict):
        return None
    number = value.get("number")
    return number if isinstance(number, int) else None


def _finding_for_resource(db: Any, repository: Repository, categories: tuple[str, ...], number: int | None) -> Finding | None:
    query = db.query(Finding).filter(
        Finding.repository_id == repository.id,
        Finding.status == "open",
        Finding.category.in_(categories),
    ).order_by(desc(Finding.detected_at))
    findings = query.limit(20).all()
    if number is not None:
        for finding in findings:
            evidence = finding.evidence or {}
            if number in (evidence.get("pr_number"), evidence.get("pull_request_number"), evidence.get("issue_number")):
                return finding
    return findings[0] if findings else None


def _finding_context(intent: BotIntent, finding: Finding) -> BotContext:
    content = extract_untrusted_content(finding.category, finding.description, finding.evidence or {})
    return BotContext(intent, SYSTEM_INSTRUCTIONS_BLOCK, wrap_untrusted_content(content), "finding")


def _api_context(intent: BotIntent, category: str, data: dict[str, Any]) -> BotContext:
    if category == "pull_requests":
        evidence = {
            "pr_title": data.get("title"),
            "description": data.get("body"),
            "file_changes": data.get("changed_files"),
        }
        description = ""
    else:
        evidence = {
            "issue_title": data.get("title"),
            "description": data.get("body"),
            "labels": [label.get("name") for label in data.get("labels", []) if isinstance(label, dict)],
            "comment_count": data.get("comments"),
        }
        description = ""
    content = extract_untrusted_content(category, description, evidence)
    return BotContext(intent, SYSTEM_INSTRUCTIONS_BLOCK, wrap_untrusted_content(content), "github")


async def _github_context(intent: BotIntent, repository: Repository, event: NormalizedWebhookEvent, number: int) -> BotContext:
    connection = repository.connection
    if connection is None:
        return BotContext(intent, SYSTEM_INSTRUCTIONS_BLOCK, wrap_untrusted_content(""), "github")
    async with GitHubAppClient(connection.installation_id) as client:
        data = await (client.get_pull_request(repository.full_name, number) if intent == BotIntent.pr_summary else client.get_issue(repository.full_name, number))
    return _api_context(intent, "pull_requests" if intent == BotIntent.pr_summary else "issues", data or {})


async def build_bot_context(
    intent: BotIntent,
    repository: Repository,
    event_payload: NormalizedWebhookEvent,
) -> BotContext | None:
    """Assemble bounded bot context from findings, with one optional GitHub read."""
    if intent == BotIntent.unknown:
        return None

    db = object_session(repository)
    if db is None:
        return None

    if intent == BotIntent.ci_status:
        finding = _finding_for_resource(db, repository, ("ci_cd", "ci"), None)
        if finding is not None:
            return _finding_context(intent, finding)
        return BotContext(
            intent,
            SYSTEM_INSTRUCTIONS_BLOCK,
            wrap_untrusted_content("No known CI failures are recorded for this repository."),
            "database",
            static_response="No known CI failures are recorded for this repository.",
        )

    if intent in (BotIntent.pr_summary, BotIntent.issue_explain):
        is_pr = intent == BotIntent.pr_summary
        category = ("pull_requests", "pull_request") if is_pr else ("issues", "issue")
        number = _resource_number(event_payload, "pull_request" if is_pr else "issue")
        finding = _finding_for_resource(db, repository, category, number)
        if finding is not None:
            evidence = finding.evidence or {}
            required = ("pr_title", "description", "file_changes") if is_pr else ("issue_title", "description")
            if all(evidence.get(key) is not None for key in required):
                return _finding_context(intent, finding)
        if number is None:
            return None
        return await _github_context(intent, repository, event_payload, number)

    if intent == BotIntent.repo_attention:
        severity_order = case((Finding.severity == "critical", 0), (Finding.severity == "high", 1), else_=2)
        findings = db.query(Finding).filter(
            Finding.repository_id == repository.id,
            Finding.status == "open",
            Finding.severity.in_(("critical", "high")),
        ).order_by(severity_order, desc(Finding.detected_at)).limit(10).all()
        snapshot = db.query(RepositoryHealthSnapshot).filter(
            RepositoryHealthSnapshot.repository_id == repository.id
        ).order_by(desc(RepositoryHealthSnapshot.computed_at)).first()
        parts = [f"[{finding.severity}] {truncate(finding.title, 300)}" for finding in findings]
        if snapshot is not None:
            parts.append("Health reasons:\n" + "\n".join(truncate(reason, 300) for reason in (snapshot.reasons or [])))
        content = "\n\n".join(parts) or "No open critical or high findings are recorded."
        return BotContext(intent, SYSTEM_INSTRUCTIONS_BLOCK, wrap_untrusted_content(content), "database")

    return None