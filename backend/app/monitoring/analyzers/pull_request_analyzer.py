from app.monitoring.analyzer_base import BaseAnalyzer, AnalyzerContext, FindingDraft

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
        
        # Consider body empty if it's None, or if it's a string that consists of only whitespace
        is_empty = body is None or not str(body).strip()
        
        if is_empty:
            title = "Pull Request opened without description"
            description = "A Pull Request was opened without a body description."
            
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
