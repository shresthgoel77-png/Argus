"""
Priority Assessment Service

This module holds deterministic priority logic.
Note on Architectural Boundaries:
Nuanced weighting (e.g., repository tier, correlation over time, component criticality) 
and AI-assisted scoring models are explicitly OUT OF SCOPE for Phase 7. Such logic 
is deferred to Phase 12 (Dashboard Intelligence) or Phase 10 (AI processing).
This step strictly relies on simple deterministic mappings.
"""

def compute_priority(*, category: str, severity: str) -> str:
    """
    Computes a finding's active priority deterministically.
    
    - 'info' severity always floors to 'low' priority, even for security.
    - Security category bumps other severities up by one tier (capped at critical).
    """
    severity = severity.lower()
    category = category.lower()

    if severity == "info":
        return "low"

    tiers = ["low", "medium", "high", "critical"]
    if severity not in tiers:
        return "low"
    
    idx = tiers.index(severity)

    if category == "security":
        idx = min(idx + 1, len(tiers) - 1)
        
    return tiers[idx]
