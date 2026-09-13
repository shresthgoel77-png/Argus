from typing import Any
from app.monitoring.analyzer_base import BaseAnalyzer, AnalyzerContext, FindingDraft


class DependencyAnalyzer(BaseAnalyzer):
    """Detects projects with an npm manifest (package.json) but no lockfile."""

    @property
    def key(self) -> str:
        return "dependency"

    @property
    def category(self) -> str:
        return "dependency"

    @property
    def requires_client(self) -> bool:
        return True

    async def analyze(self, context: AnalyzerContext) -> list[FindingDraft]:
        """Check for missing lockfiles when an npm manifest is present."""
        if not context.client:
            return []

        npm_lockfiles = ["package-lock.json", "yarn.lock", "pnpm-lock.yaml"]
        from app.integrations.github.exceptions import GitHubAuthError

        try:
            # Check if package.json exists
            # We assume it is an npm ecosystem for Phase 6.
            # Pip/requirements.txt and other ecosystems follow an identical pattern 
            # and could be a natural next analyzer or extension, not built here.
            manifest = await context.client.get_repository_content(
                context.repository.full_name, "package.json"
            )

            # If package.json is missing, nothing to do
            if not manifest:
                return []

            # package.json is present, check for lockfiles
            for lockfile in npm_lockfiles:
                lock_content = await context.client.get_repository_content(
                    context.repository.full_name, lockfile
                )
                if lock_content is not None:
                    # Found at least one lockfile, all good
                    return []

            # Manifiest found, but no known lockfile was found
            return [
                FindingDraft(
                    category=self.category,
                    type_="missing_lockfile",
                    title="Missing Lockfile",
                    description=(
                        "Found package.json but no corresponding package-lock.json, "
                        "yarn.lock, or pnpm-lock.yaml was found."
                    ),
                    severity="medium",
                    evidence={"manifest": "package.json"},
                )
            ]

        except GitHubAuthError:
            # 403 on client fetch -> treated as "skipped due to permissions," not a crash
            return []
