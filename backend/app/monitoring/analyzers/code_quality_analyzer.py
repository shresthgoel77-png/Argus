from typing import Any
from app.monitoring.analyzer_base import BaseAnalyzer, AnalyzerContext, FindingDraft
from app.integrations.github.exceptions import GitHubAuthError
from app.integrations.github.client import get_branch_protection


class CodeQualityAnalyzer(BaseAnalyzer):
    """Checks if branch protection is enabled on the repository's default branch."""

    @property
    def key(self) -> str:
        return "code_quality"

    @property
    def category(self) -> str:
        return "code_quality"

    @property
    def requires_client(self) -> bool:
        return True

    full_state_sync: bool = True

    async def analyze(self, context: AnalyzerContext) -> list[FindingDraft]:
        if not context.client:
            raise RuntimeError("Branch protection scan requires a GitHub client")
            
        try:
            installation_id = context.repository.connection.installation_id
            protection = await get_branch_protection(
                installation_id, context.repository.full_name, context.repository.default_branch
            )
        except GitHubAuthError:
            raise

        if protection is None:
            # 404 naturally returns None from client.py get_branch_protection
            return [
                FindingDraft(
                    category=self.category,
                    type_="missing_branch_protection",
                    title=f"Missing Branch Protection: {context.repository.default_branch}",
                    description=f"Branch protection is not configured for the default branch '{context.repository.default_branch}'.",
                    severity="medium",
                    evidence={"default_branch": context.repository.default_branch},
                    fingerprint=f"code_quality:{context.repository.id}:branch_protection:{context.repository.default_branch}",
                )
            ]

        # Protection is configured (not None)
        return []
