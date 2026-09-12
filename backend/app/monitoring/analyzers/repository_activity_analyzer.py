from app.monitoring.analyzer_base import BaseAnalyzer, AnalyzerContext, FindingDraft
from typing import List

class RepositoryActivityAnalyzer(BaseAnalyzer):
    key = "repository_activity"
    category = "repository_activity"
    requires_client = False
    
    def analyze(self, context: AnalyzerContext) -> List[FindingDraft]:
        if context.normalized_event.event_type != "push":
            return []
            
        if not context.normalized_event.forced:
            return []
            
        default_branch = context.repository.default_branch or "main"
        expected_ref = f"refs/heads/{default_branch}"
        
        if context.normalized_event.ref == expected_ref:
            return [
                FindingDraft(
                    category=self.category,
                    type_="force_push_default_branch",
                    severity="medium",
                    title="Force Push to Default Branch",
                    description=f"A force push was executed on the default branch ({default_branch}).",
                    evidence={},
                )
            ]
            
        return []
