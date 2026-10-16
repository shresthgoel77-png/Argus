from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.github.client import GitHubAppClient
from app.models.repository import Repository
from app.monitoring.analyzer_base import (
    BaseAnalyzer,
    AnalyzerContext,
    FindingDraft
)
from app.services import finding_service


class PullRequestAnalyzer(BaseAnalyzer):
    key = "pull_request"
    category = "pull_request"
    requires_client = False

    def analyze(self, context: AnalyzerContext) -> list[FindingDraft]:
        ev = context.normalized_event
        if not ev or ev.event_type != "pull_request" or ev.action != "opened":
            return []

        pr = ev.raw_payload.get("pull_request", {})
        body = pr.get("body")

        # Consider body empty if it's None, or if it's a string that consists
        # of only whitespace
        is_empty = body is None or not str(body).strip()

        if is_empty:
            title = "Pull Request opened without description"
            description = (
                "A Pull Request was opened without "
                "a body description."
            )

            evidence = {
                "pull_request_url": pr.get("html_url"),
                "pull_request_number": pr.get("number"),
            }

            finding = FindingDraft(
                category=self.category,
                type_="pull_request_opened_without_description",
                title=title,
                description=description,
                severity="info",
                evidence=evidence,
            )

            return [finding]

        return []

    async def scan_repository_for_stale_prs(
        self, db: Session, repository: Repository, client: GitHubAppClient
    ) -> None:
        items = await client.list_repository_pulls(repository.full_name)
        now = datetime.now(timezone.utc)
        threshold = timedelta(days=settings.stale_pr_days)
        drafts = []
        # Validate the entire response before persisting or resolving anything.
        for item in items:
            if (not isinstance(item, dict) or type(item.get("number")) is not int
                    or not item.get("updated_at") or not item.get("html_url")):
                raise ValueError("GitHub returned incomplete pull requests evidence")
            updated_at = datetime.fromisoformat(item["updated_at"].replace("Z", "+00:00"))
            if updated_at.tzinfo is None:
                raise ValueError("GitHub returned a timestamp without a timezone")
            if now - updated_at > threshold:
                number = item["number"]
                drafts.append(FindingDraft(
                    category=self.category, type_="stale_pull_request",
                    title=f"Stale Pull Request #{number}",
                    description=f"Pull Request #{number} has been stale for over {settings.stale_pr_days} days.",
                    severity="info",
                    evidence={"pull_request_url": item["html_url"], "pull_request_number": number,
                              "updated_at": updated_at.isoformat()},
                    fingerprint=f"stale_pull_request_{number}",
                ))
        finding_service.sync_findings_for_run(
            db, repository_id=repository.id, category=self.category,
            analyzer_key=self.key, drafts=drafts,
            source=f"repository_scan:{self.key}", finding_type="stale_pull_request",
        )
