import datetime
from app.models import Incident, Evidence, RemediationAction, VerificationResult
from app.investigation.timeline import build_timeline

def format_timestamp(ts: datetime.datetime | str | None) -> str:
    if not ts:
        return "Unknown"
    if isinstance(ts, str):
        try:
            return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S UTC")
        except ValueError:
            return ts
    return ts.strftime("%Y-%m-%d %H:%M:%S UTC")

def build_rca_report(
    incident: Incident,
    evidence_rows: list[Evidence],
    remediation_action: RemediationAction | None,
    verification_result: VerificationResult | None
) -> str:
    """Assembles a Markdown report for an incident from real persisted data only."""
    
    # Extract ai_rca and git evidence rows
    ai_rca_row = next((e for e in evidence_rows if e.category == "ai_rca"), None)
    git_row = next((e for e in evidence_rows if e.category == "observed_fact" and e.content and e.content.get("source") == "git"), None)
    
    ai_rca = ai_rca_row.content if ai_rca_row and ai_rca_row.content else {}
    
    # Evidence mapping for Supporting Evidence summary
    evidence_map = {str(e.id): e for e in evidence_rows}
    
    # 1. Header
    report = []
    report.append(f"# Incident Report: {incident.type} — {incident.service} ({incident.severity})")
    report.append(f"**Status:** {incident.status} **Incident ID:** {incident.id} **Detected:** {format_timestamp(incident.timestamp)}")
    report.append("")
    
    # 2. Summary
    report.append("## Summary")
    if ai_rca_row:
        report.append(ai_rca.get("summary", "No summary available."))
    else:
        report.append("RCA not yet run.")
    report.append("")
    
    # 3. Impact (only if ai_rca exists)
    if ai_rca_row and "impact" in ai_rca:
        report.append("## Impact")
        report.append(ai_rca.get("impact"))
        report.append("")
    
    # 4. Affected Components
    report.append("## Affected Components")
    if ai_rca_row and "affected_components" in ai_rca:
        for comp in ai_rca.get("affected_components", []):
            report.append(f"- {comp}")
    else:
        report.append("RCA not yet run.")
    report.append("")
    
    # 5. Timeline
    report.append("## Timeline")
    timeline_entries = build_timeline(incident, evidence_rows)
    if timeline_entries:
        for entry in timeline_entries:
            ts = format_timestamp(entry["timestamp"])
            report.append(f"- **{ts}**: {entry['description']}")
    else:
        report.append("- No timeline events.")
    report.append("")
    
    # 6. Root Cause & Confidence
    report.append("## Root Cause")
    if ai_rca_row:
        report.append(ai_rca.get("root_cause", "No root cause available."))
        report.append("")
        report.append(f"**Confidence:** {ai_rca.get('confidence', 'unknown').capitalize()}")
    else:
        report.append("RCA not yet run.")
    report.append("")
    
    # 7. Alternative Hypotheses
    report.append("## Alternative Hypotheses")
    if ai_rca_row:
        alt_hyps = ai_rca.get("alternative_hypotheses", [])
        if alt_hyps:
            for alt in alt_hyps:
                report.append(f"- {alt}")
        else:
            report.append("None provided.")
    else:
        report.append("RCA not yet run.")
    report.append("")
    
    # 8. Supporting Evidence
    report.append("## Supporting Evidence")
    if ai_rca_row:
        sup_evidence_ids = ai_rca.get("supporting_evidence", [])
        if sup_evidence_ids:
            for idx, eid in enumerate(sup_evidence_ids):
                if idx >= 10:
                    remaining = len(sup_evidence_ids) - 10
                    report.append(f"(+{remaining} more evidence items in the dashboard)")
                    break
                row = evidence_map.get(str(eid))
                if row:
                    content = row.content or {}
                    summary = f"Evidence #{eid} ({row.category})"
                    source = content.get("source", "")
                    # Create a short real summary based on category
                    if row.category == "observed_fact" and source == "git":
                        commits = content.get("commits", [])
                        if commits:
                            commit = commits[0]
                            sha = commit.get("sha", "")[:7]
                            msg = commit.get("message", "").split("\n")[0]
                            summary = f"commit {sha}: {msg}"
                        else:
                            summary = "git history checked"
                    elif row.category == "observed_fact" and source == "metrics":
                        signal = content.get("signal", "metric")
                        datapoints = content.get("datapoints", [])
                        if datapoints:
                            peak_val = max([float(dp[1]) for dp in datapoints if len(dp) > 1] or [0])
                            summary = f"{signal} peak value {peak_val}"
                    elif row.category == "observed_fact" and source == "logs":
                        matched = content.get("matched_lines", [])
                        summary = f"{len(matched)} matched log lines"
                    report.append(f"- {summary}")
                else:
                    report.append(f"- Evidence #{eid} (Not found in current dataset)")
        else:
            report.append("No supporting evidence specified.")
    else:
        report.append("RCA not yet run.")
    report.append("")
    
    # 9. Relevant Git Change
    report.append("## Relevant Git Change")
    if git_row:
        content = git_row.content or {}
        commits = content.get("commits", [])
        if commits:
            for commit in commits:
                sha = commit.get("sha", "")[:7]
                msg = commit.get("message", "").strip()
                files = commit.get("files", [])
                files_str = f" ({len(files)} files changed)" if files else ""
                report.append(f"- **{sha}**: {msg}{files_str}")
        else:
            report.append("No correlated commit found in the investigation window.")
    else:
        report.append("No git evidence gathered.")
    report.append("")
    
    # 10. Recommended Fix
    report.append("## Recommended Fix")
    if ai_rca_row:
        report.append(ai_rca.get("recommended_fix", "No fix recommended."))
    else:
        report.append("RCA not yet run.")
    report.append("")
    
    # 11. Remediation
    report.append("## Remediation")
    if remediation_action:
        ra = remediation_action
        report.append(f"- **Action Type:** {ra.action_type}")
        report.append(f"- **Risk Level:** {ra.risk_level.capitalize() if ra.risk_level else 'Unknown'}")
        report.append(f"- **Status:** {ra.status}")
        report.append(f"- **Approved By:** {ra.approved_by or 'N/A'}")
        report.append(f"- **Executed At:** {format_timestamp(ra.executed_at) if ra.executed_at else 'N/A'}")
        
        if ra.result:
            result = ra.result
            if isinstance(result, dict) and 'commit_sha' in result:
                report.append(f"- **Result Summary:** Executed commit {result['commit_sha']}")
            elif isinstance(result, dict) and 'success' in result:
                status = "Success" if result['success'] else "Failed"
                report.append(f"- **Result Summary:** Application of remediation: {status}")
            else:
                report.append(f"- **Result Summary:** {str(result)}")
        else:
            report.append("- **Result Summary:** No execution result yet.")
    else:
        report.append("No remediation action has been proposed yet.")
    report.append("")
    
    # 12. Verification Result
    report.append("## Verification Result")
    if verification_result:
        vr = verification_result
        if vr.recovered:
            status_text = "Recovery verified."
        else:
            status_text = "Recovery NOT verified within the wait window."
            
        report.append(f"**{status_text}**")
        
        before_metrics = vr.before_metrics or {}
        after_metrics = vr.after_metrics or {}
        
        before_firing = before_metrics.get("firing", "Unknown")
        before_val = before_metrics.get("value", "Unknown")
        
        after_detector = after_metrics.get("final_detector_result", {}) if isinstance(after_metrics, dict) else {}
        after_firing = after_detector.get("firing", "Unknown")
        after_val = after_detector.get("value", "Unknown")
        
        report.append(f"- **Before:** Detector firing: {before_firing}, Value: {before_val}")
        report.append(f"- **After:** Detector firing: {after_firing}, Value: {after_val}")
    else:
        report.append("Verification has not been run yet.")
    report.append("")
    
    # 13. Footer
    now_ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    report.append("---")
    report.append(f"*Auto-generated by AI Reliability Engineer at {now_ts}. Reflects system state at generation time only.*")
    
    return "\\n".join(report)
