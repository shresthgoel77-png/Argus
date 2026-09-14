from typing import Sequence
import math

# We can import Finding for type hinting if we want, but since they are pure, 
# it's even purer if it just assumes something with a `.category` and `.severity` or we use Finding type directly.
from app.models.finding import Finding

FINDING_CATEGORY_TO_HEALTH_CATEGORY = {
    "ci": "ci_cd",
    "pull_request": "pull_requests",
    "issue": "issues",
    "dependency": "dependencies",
    "security": "security",
    "code_quality": "code_quality",
    "repository_activity": "ci_cd"
}

HEALTH_CATEGORIES = [
    "ci_cd", 
    "dependencies", 
    "security", 
    "issues", 
    "pull_requests", 
    "code_quality"
]

SEVERITY_DEDUCTIONS = {
    "critical": 40,
    "high": 20,
    "medium": 10,
    "low": 5,
    "info": 0
}

def compute_category_scores(open_findings: Sequence[Finding]) -> dict[str, int]:
    """
    Computes a score [0, 100] for each configured HEALTH_CATEGORIES.
    Deductions are based on severity of each mapped finding.
    """
    scores = {category: 100 for category in HEALTH_CATEGORIES}
    
    for finding in open_findings:
        if finding.category not in FINDING_CATEGORY_TO_HEALTH_CATEGORY:
            continue
            
        health_cat = FINDING_CATEGORY_TO_HEALTH_CATEGORY[finding.category]
        if health_cat not in scores:
            continue
            
        deduction = SEVERITY_DEDUCTIONS.get(finding.severity, 0)
        scores[health_cat] -= deduction
        
    for category in scores:
        scores[category] = max(0, min(100, scores[category]))
        
    return scores

def compute_overall_score(category_scores: dict[str, int]) -> int:
    """
    Computes an unweighted average of the fixed category scores.
    """
    if not category_scores:
        return 100
        
    # As per prompt, unweighted average across all 6 fixed categories, rounded, clamped to [0, 100]
    total_score = 0
    for val in category_scores.values():
        total_score += val
        
    avg = total_score / len(category_scores)
    
    # Simple rounding
    score = int(round(avg))
    
    return max(0, min(100, score))
