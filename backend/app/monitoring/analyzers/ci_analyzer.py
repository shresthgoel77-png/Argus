from app.monitoring.analyzer_base import BaseAnalyzer, AnalyzerContext, FindingDraft

class CIAnalyzer(BaseAnalyzer):
    key = "ci"
    category = "ci"
    requires_client = False

    def analyze(self, context: AnalyzerContext) -> list[FindingDraft]:
        ev = context.normalized_event
        if not ev or ev.event_type != "workflow_run" or ev.action != "completed":
            return []

        conclusion = ev.workflow_run_conclusion

        severity = None
        type_ = None

        if conclusion in ("failure", "timed_out"):
            severity = "high"
            type_ = "workflow_run_failed"
        elif conclusion == "cancelled":
            severity = "low"
            type_ = "workflow_run_cancelled"
        else:
            return []

        title = f"Workflow '{ev.workflow_run_name}' {conclusion}"
        description = f"The GitHub Actions workflow '{ev.workflow_run_name}' completed with conclusion: '{conclusion}'."
        
        evidence = {
            "workflow_name": ev.workflow_run_name,
            "run_id": ev.workflow_run_id,
            "conclusion": conclusion,
            "url": ev.workflow_run_url,
        }

        finding = FindingDraft(
            category=self.category,
            type_=type_,
            title=title,
            description=description,
            severity=severity,
            evidence=evidence,
        )

        return [finding]
