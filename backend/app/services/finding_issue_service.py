"""Preview and explicitly approved publication of evidence-backed findings."""
import hashlib
import json

from fastapi import BackgroundTasks, HTTPException
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import String, cast, or_, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.github.client import GitHubAppClient
from app.integrations.github.exceptions import GitHubAPIError
from app.models.finding import Finding
from app.schemas.finding import FindingIssuePreview
from app.services.finding_service import get_finding_or_404
from app.services.issue_notification_service import send_issue_created_email


logger = get_logger(__name__)


def _serializer():
    return URLSafeTimedSerializer(settings.session_secret_key, salt="finding-issue-preview")


def preview_issue(finding: Finding) -> FindingIssuePreview:
    evidence = {k: v for k, v in finding.evidence.items() if k != "_github_issue"}
    if (finding.status not in {"open", "acknowledged"} or not evidence
            or not finding.source.startswith(("on_demand:", "webhook:", "repository_scan:"))):
        raise HTTPException(409, "Issue generation requires an active finding with analyzer evidence.")
    if finding.repository.connection.status != "active":
        raise HTTPException(409, "Reconnect the GitHub App installation before creating an issue.")

    check = {"ci": "ci_cd", "issue": "stale_issues", "pull_request": "stale_prs"}.get(
        finding.category, finding.category
    )
    assessment = finding.repository.monitoring_checks.get(check)
    if not isinstance(assessment, dict) or assessment.get("status") != "success":
        raise HTTPException(409, "Re-scan this finding successfully before generating an issue.")
    # A successful age check does not verify a webhook's missing-description condition.
    supported_types = {
        "security": {"dependabot_alert_open"}, "dependency": {"missing_lockfile"},
        "code_quality": {"missing_branch_protection"}, "issue": {"stale_issue"},
        "pull_request": {"stale_pull_request"},
        "ci": {"workflow_run_failure", "workflow_run_timed_out", "workflow_run_cancelled",
               "workflow_run_action_required", "workflow_run_stale", "workflow_run_startup_failure"},
    }
    if finding.source.startswith("webhook:") or finding.type not in supported_types.get(finding.category, set()):
        raise HTTPException(409, "This finding's condition has not been verified by the relevant repository assessment.")
    evidence_fields = {
        "security": ("github_alert_number", "manifest_path"),
        "dependency": ("manifest",), "code_quality": ("default_branch",),
        "ci": ("run_id", "url"), "issue": ("issue_number", "issue_url"),
        "pull_request": ("pull_request_number", "pull_request_url"),
    }
    if not all(evidence.get(field) for field in evidence_fields.get(finding.category, ())):
        raise HTTPException(409, "Issue generation requires identifiable source evidence from the relevant analyzer.")

    remediation = {
        "missing_lockfile": "Generate and commit a lockfile using the project's package manager, then re-run the dependency check.",
        "dependabot_alert_open": "Review the linked advisory and affected dependency. Upgrade to a patched version and run the project's tests.",
        "missing_branch_protection": "Review the default branch's protection requirements and configure the appropriate review and status checks.",
    }.get(finding.type, "Investigate the recorded evidence, address the reported condition, and re-run the relevant check.")
    title = f"[{finding.severity}] {finding.title}"[:256]
    body = (
        f"## Finding\n{finding.description}\n\n"
        f"- Repository: {finding.repository.full_name}\n"
        f"- Finding: {finding.id}\n- Category: {finding.category}\n"
        f"- Severity: {finding.severity}\n- Status: {finding.status}\n"
        f"- Analyzer source: {finding.source}\n- Detected: {finding.detected_at.isoformat()}\n\n"
        "## Recorded evidence\n```json\n"
        f"{json.dumps(evidence, indent=2, sort_keys=True)}\n```\n\n"
        f"## Suggested next steps\n{remediation}\n\n"
        "## Verification\nConfirm the reported condition against the evidence, run the relevant tests, "
        "and re-scan the repository after the fix. File and line locations are included only when reported by the source.\n\n"
        f"<!-- repomedic-finding:{finding.id} -->"
    )
    if len(body) > 60000:
        raise HTTPException(409, "The finding evidence exceeds the issue preview size limit.")
    digest = hashlib.sha256((title + "\n" + body).encode()).hexdigest()
    return FindingIssuePreview(
        repository=finding.repository.full_name, title=title, body=body,
        preview_token=_serializer().dumps([str(finding.id), digest]),
    )


async def create_issue(
    db: Session, *, user_id, finding_id, preview_token: str,
    background_tasks: BackgroundTasks, recipient_email: str | None,
    recipient_auth_provider: str, recipient_external_id: str | None,
):
    finding = get_finding_or_404(db, user_id, finding_id)
    preview = preview_issue(finding)
    try:
        approved = _serializer().loads(preview_token, max_age=900)
        current = _serializer().loads(preview.preview_token)
        if approved != current:
            raise BadSignature("Finding changed")
    except (BadSignature, SignatureExpired):
        raise HTTPException(409, "The preview expired or the finding changed. Review a new preview.")

    previous = finding.evidence.get("_github_issue", {})
    if previous.get("status") == "created":
        return previous["item"]
    marker = f"<!-- repomedic-finding:{finding.id} -->"
    async with GitHubAppClient(finding.repository.connection.installation_id) as client:
        # Include closed issues: closing an issue must not permit duplicate publication.
        issues = await client.list_repository_issues(finding.repository.full_name, state="all")
        existing = next((i for i in issues if "pull_request" not in i and marker in (i.get("body") or "")), None)
        if existing:
            finding.evidence = {**finding.evidence, "_github_issue": {"status": "created", "item": existing}}
            db.commit()
            return existing
        if previous.get("status") in {"pending", "unknown"}:
            raise HTTPException(409, "The previous GitHub request has an uncertain outcome. Check GitHub before retrying; no second issue was sent.")

        # Atomically claim publication, including on SQLite where FOR UPDATE is ignored.
        state = Finding.evidence["_github_issue"]["status"].as_string()
        # SQLite CURRENT_TIMESTAMP omits fractional seconds, unlike bound datetimes.
        version = (cast(Finding.updated_at, String) == str(finding.updated_at)
                   if db.get_bind().dialect.name == "sqlite"
                   else Finding.updated_at == finding.updated_at)
        claimed = db.execute(
            update(Finding).where(
                Finding.id == finding.id,
                version,
                Finding.status == finding.status,
                or_(state.is_(None), state == "failed"),
            ).values(evidence={**finding.evidence, "_github_issue": {"status": "pending"}}),
            execution_options={"synchronize_session": False},
        ).rowcount
        db.commit()
        if not claimed:
            raise HTTPException(409, "Issue creation is already in progress. Refresh before trying again.")
        db.refresh(finding)
        try:
            item = await client.create_repository_issue(
                finding.repository.full_name, title=preview.title, body=preview.body,
            )
            # An invalid success response is also ambiguous: never blindly POST again.
            if not item.get("number") or not item.get("html_url"):
                raise ValueError("GitHub returned an invalid issue response")
        except Exception as exc:
            db.refresh(finding)
            definitive = isinstance(exc, GitHubAPIError) and exc.response_status in {401, 403, 404, 410, 422, 429}
            finding.evidence = {**finding.evidence, "_github_issue": {"status": "failed" if definitive else "unknown"}}
            db.commit()
            if definitive:
                raise
            raise HTTPException(502, "GitHub did not confirm issue creation. Check GitHub before retrying; the request will not be sent twice.") from exc
        db.refresh(finding)
        finding.evidence = {**finding.evidence, "_github_issue": {"status": "created", "item": item}}
        db.commit()
        try:
            background_tasks.add_task(
                send_issue_created_email,
                user_id=str(user_id), recipient_email=recipient_email,
                auth_provider=recipient_auth_provider, external_id=recipient_external_id,
                finding_id=str(finding.id), repository_name=preview.repository,
                issue_title=item.get("title") or preview.title, issue_url=item["html_url"],
                category=finding.category, severity=finding.severity,
                description=finding.description,
            )
        except Exception:
            logger.warning("Issue email scheduling failed")
        return item
