from typing import Any
from app.monitoring.analyzer_base import BaseAnalyzer, AnalyzerContext, FindingDraft
from app.integrations.github.exceptions import GitHubAuthError
import logging

logger = logging.getLogger(__name__)


def _map_severity(github_severity: str) -> str:
    """Map GitHub Security Advisory severity to our model."""
    mapping = {
        "critical": "critical",
        "high": "high",
        "medium": "medium",
        "low": "low",
    }
    return mapping.get(github_severity.lower(), "low")


class SecurityAnalyzer(BaseAnalyzer):
    """Surfaces GitHub's Dependabot alerts as findings."""

    @property
    def key(self) -> str:
        return "security"

    @property
    def category(self) -> str:
        return "security"

    @property
    def requires_client(self) -> bool:
        return True

    full_state_sync: bool = True

    async def analyze(self, context: AnalyzerContext) -> list[FindingDraft]:
        """Fetch open Dependabot alerts and create findings for them.
        
        Note: Re-running this analyzer will currently re-create a finding per 
        open alert each time. This is an accepted Phase 6 limitation. 
        Deduplication is Phase 7's job.
        
        Note on Permissions: This analyzer depends on the 'Dependabot-alerts' 
        permission on the GitHub App to fetch the alerts successfully. 
        If missing, it results in a 403.
        """
        if not context.client:
            return []

        try:
            alerts = await context.client.list_dependabot_alerts(context.repository.full_name)
        except GitHubAuthError:
            # 403 on client fetch -> treated as "skipped due to permissions," not a crash
            return []
        
        # 404 is natively managed within list_dependabot_alerts returning []
        findings: list[FindingDraft] = []
        for alert in alerts:
            if alert.get("state") != "open":
                continue
            
            advisory = alert.get("security_advisory", {})
            gh_severity = advisory.get("severity", "low")
            mapped_severity = _map_severity(gh_severity)

            summary = advisory.get("summary", "Unknown Security Advisory")
            dependency_package = alert.get("dependency", {}).get("package", {})
            package_name = dependency_package.get("name", "unknown")

            findings.append(
                FindingDraft(
                    category=self.category,
                    type_="dependabot_alert_open",
                    title=f"Dependabot Alert: {package_name}",
                    description=summary,
                    severity=mapped_severity,
                    evidence={
                        "github_alert_number": alert.get("number"),
                        "package_name": package_name,
                        "severity": gh_severity,
                    },
                    fingerprint=f"security:{context.repository.id}:dependabot:{alert.get('number')}",
                )
            )

        return findings
