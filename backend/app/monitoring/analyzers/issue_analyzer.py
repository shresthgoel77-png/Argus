from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.github.client import GitHubAppClient
from app.models.repository import Repository
from app.monitoring.analyzer_base import BaseAnalyzer, AnalyzerContext, FindingDraft
from app.services import finding_service

class IssueAnalyzer(BaseAnalyzer):
    key = "issue"
    category = "issue"
    requires_client = False

    def analyze(self, context: AnalyzerContext) -> list[FindingDraft]:
        ev = context.normalized_event
        if not ev or ev.event_type != "issues" or ev.action != "opened":
            return []

        issue = ev.raw_payload.get("issue", {})
        body = issue.get("body")
        
        # Consider body empty if it's None, or if it's a string that consists of only whitespace
        is_empty = body is None or not str(body).strip()
        
        if is_empty:
            title = "Issue opened without description"
            description = "An Issue was opened without a body description."
            
            evidence = {
                "issue_url": issue.get("html_url"),
                "issue_number": issue.get("number"),
            }

            finding = FindingDraft(
                category=self.category,
                type_="issue_opened_without_description",
                title=title,
                description=description,
                severity="info",
                evidence=evidence,
            )

            return [finding]
            
        return []

    async def scan_repository_for_stale_issues(self, db: Session, repository: Repository, client: GitHubAppClient) -> None:
        issues = await client.list_repository_issues(repository.full_name)
        now = datetime.now(timezone.utc)
        threshold = timedelta(days=settings.stale_issue_days)
        
        for issue in issues:
            if "pull_request" in issue:
                continue
                
            updated_at_str = issue.get("updated_at")
            if not updated_at_str:
                continue
                
            updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
            if now - updated_at > threshold:
                issue_number = issue.get("number")
                fingerprint = f"stale_issue_{issue_number}"
                title = f"Stale Issue #{issue_number}"
                description = f"Issue #{issue_number} has been stale for over {settings.stale_issue_days} days."
                
                evidence = {
                    "issue_url": issue.get("html_url"),
                    "issue_number": issue_number,
                    "updated_at": updated_at.isoformat(),
                }
                
                finding_service.create_finding(
                    db,
                    repository_id=repository.id,
                    category=self.category,
                    type_="stale_issue",
                    title=title,
                    description=description,
                    severity="info",
                    source=f"repository_scan:{self.key}",
                    evidence=evidence,
                    fingerprint=fingerprint,
                )
