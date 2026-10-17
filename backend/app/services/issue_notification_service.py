"""Best-effort email for a newly confirmed GitHub issue, after the response."""
from html import escape
from uuid import UUID
from urllib.parse import urlsplit

from clerk_backend_api import Clerk

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.integrations.email import get_provider
from app.models.ai_analysis import AIAnalysis

logger = get_logger(__name__)


def send_issue_created_email(
    *, user_id: str, recipient_email: str | None, auth_provider: str,
    external_id: str | None, finding_id: str, repository_name: str,
    issue_title: str, issue_url: str, category: str | None,
    severity: str | None, description: str | None,
) -> None:
    """Receive only snapshots of the initiating identity and confirmed issue.

    This synchronous callback runs in FastAPI's background thread pool. Never
    pass the request's SQLAlchemy session or ORM objects into it.
    """
    try:
        if not (settings.smtp_host and settings.smtp_username
                and settings.smtp_password and settings.smtp_password.get_secret_value()
                and settings.clerk_secret_key and settings.clerk_secret_key.get_secret_value()
                and recipient_email and auth_provider == "clerk" and external_id):
            return
        # Use the initiating authenticated identity, never the repository owner.
        identity = Clerk(bearer_auth=settings.clerk_secret_key.get_secret_value()).users.get(
            user_id=external_id,
        )
        if identity.id != external_id:
            return
        recipient = next((address.email_address for address in identity.email_addresses
                          if address.email_address.casefold() == recipient_email.casefold()
                          and getattr(address.verification, "status", None) == "verified"), None)
        if not recipient:
            return
        url = urlsplit(issue_url)
        if url.scheme != "https" or url.hostname != "github.com" or url.username or url.password:
            logger.warning("Issue email skipped: invalid GitHub link")
            return

        summary = None
        try:
            with SessionLocal() as db:
                analysis = db.query(AIAnalysis).filter(
                    AIAnalysis.finding_id == UUID(finding_id),
                    AIAnalysis.status == "completed",
                    AIAnalysis.summary.is_not(None),
                ).order_by(AIAnalysis.requested_at.desc()).first()
                if analysis:
                    summary = analysis.summary
        except Exception:
            logger.warning("Issue email AI summary lookup failed")

        fields = [("Repository", repository_name), ("Issue title", issue_title),
                  ("Category", category), ("Severity", severity),
                  ("Description", description), ("AI summary", summary)]
        html_body = "".join(
            f"<p><strong>{label}:</strong> {escape(value).replace(chr(10), '<br>')}</p>"
            for label, value in fields if value
        )
        html_body += f'<p><a href="{escape(issue_url, quote=True)}">View issue on GitHub</a></p>'
        text_body = "\n\n".join(f"{label}: {value}" for label, value in fields if value)
        text_body += f"\n\nGitHub issue: {issue_url}"
        result = get_provider("smtp")().send(
            to=recipient, subject=f"RepoMedic issue created: {issue_title}",
            html_body=html_body, text_body=text_body,
        )
        if not result.success:
            logger.warning("Issue email delivery failed", extra={"user_id": user_id})
    except Exception:
        # Do not log exception details, email addresses, bodies, or credentials.
        logger.warning("Issue email delivery failed", extra={"user_id": user_id})
