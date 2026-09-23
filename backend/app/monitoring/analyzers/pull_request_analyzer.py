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
        self,
        db: Session,
        repository: Repository,
        client: GitHubAppClient
    ) -> None:
        prs = await client.list_repository_pulls(repository.full_name)
        now = datetime.now(timezone.utc)
        threshold = timedelta(days=settings.stale_pr_days)

        for pr in prs:
            updated_at_str = pr.get("updated_at")
            if not updated_at_str:
                continue

            updated_at = datetime.fromisoformat(
                updated_at_str.replace("Z", "+00:00")
            )
            if now - updated_at > threshold:
                pr_number = pr.get("number")
                fingerprint = f"stale_pull_request_{pr_number}"
                title = f"Stale Pull Request #{pr_number}"
                description = (
                    f"Pull Request #{pr_number} has been "
                    f"stale for over {settings.stale_pr_days} days."
                )

                evidence = {
                    "pull_request_url": pr.get("html_url"),
                    "pull_request_number": pr_number,
                    "updated_at": updated_at.isoformat(),
                }

                finding_service.create_finding(
                    db,
                    repository_id=repository.id,
                    category=self.category,
                    type_="stale_pull_request",
                    title=title,
                    description=description,
                    severity="info",
                    source=f"repository_scan:{self.key}",
                    evidence=evidence,
                    fingerprint=fingerprint,
                )
