from typing import Any
from app.monitoring.analyzer_base import BaseAnalyzer, AnalyzerContext, FindingDraft
from app.integrations.github.exceptions import GitHubAuthError, GitHubAPIError
import logging

logger = logging.getLogger(__name__)


def security_failure_reason(error: Exception) -> str:
    """Classify known upstream failures without exposing arbitrary response text."""
    if isinstance(error, GitHubAPIError):
        status = error.response_status
        message = str(error).lower()
        if status == 403 and "dependabot alerts are disabled for this repository" in message:
            return "GitHub reports Dependabot alerts are disabled for this repository. Enable alerts in GitHub, then reassess."
        if status == 429 or (status == 403 and "rate limit" in message):
            return "GitHub rate limit prevented the security check. Retry after the rate limit resets."
        if status == 401:
            return "GitHub rejected authentication for the security check. Verify the existing GitHub App installation, then retry."
        if status == 403:
            return "GitHub denied access to Dependabot alerts (HTTP 403). Verify the App's Dependabot alerts read permission and repository access."
        if status == 404:
            return "GitHub could not provide Dependabot alerts (HTTP 404). Verify repository access and alert availability."
        if status == 400:
            return "GitHub rejected the Dependabot alerts request (HTTP 400). Inspect the backend logs for an unsupported request parameter."
        return "GitHub could not complete the security request. Retry; if it persists, inspect the backend logs."
    return "The security check failed unexpectedly. Retry; if it persists, inspect the backend logs."


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
        
        Note on Permissions: This analyzer depends on the 'Dependabot-alerts' 
        permission on the GitHub App to fetch the alerts successfully. 
        If missing, it results in a 403.
        """
        if not context.client:
            raise RuntimeError("Security scan requires a GitHub client")

        try:
            alerts = await context.client.list_dependabot_alerts(context.repository.full_name)
        except GitHubAuthError:
            raise
        
        findings: list[FindingDraft] = []
        for alert in alerts:
            if not isinstance(alert.get("number"), int) or not alert.get("state"):
                raise ValueError("GitHub returned an incomplete Dependabot alert")
            if alert.get("state") != "open":
                continue
            
            advisory = alert.get("security_advisory", {})
            gh_severity = advisory.get("severity", "low")
            mapped_severity = _map_severity(gh_severity)

            summary = advisory.get("summary", "Unknown Security Advisory")
            dependency_package = alert.get("dependency", {}).get("package", {})
            package_name = dependency_package.get("name")
            if not package_name or not advisory.get("summary") or advisory.get("severity") not in {"critical", "high", "medium", "low"}:
                raise ValueError("GitHub returned incomplete security advisory evidence")

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
                        **({"manifest_path": alert["dependency"]["manifest_path"]}
                           if alert.get("dependency", {}).get("manifest_path") else {}),
                        **({"url": alert["html_url"]} if alert.get("html_url") else {}),
                    },
                    fingerprint=f"security:{context.repository.id}:dependabot:{alert.get('number')}",
                )
            )

        return findings
