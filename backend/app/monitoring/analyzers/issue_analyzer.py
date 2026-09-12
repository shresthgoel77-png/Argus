from app.monitoring.analyzer_base import BaseAnalyzer, AnalyzerContext, FindingDraft

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
