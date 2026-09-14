import pytest
import uuid
from app.services.health_score_service import compute_category_scores, compute_overall_score
from app.models.finding import Finding

def create_mock_finding(category: str, severity: str) -> Finding:
    f = Finding()
    f.id = uuid.uuid4()
    f.category = category
    f.severity = severity
    return f

def test_zero_findings():
    scores = compute_category_scores([])
    assert all(score == 100 for score in scores.values()), "Zero findings should result in 100 for all categories"
    assert len(scores) == 6, "Expected exactly 6 categories"
    
    overall = compute_overall_score(scores)
    assert overall == 100, "Overall score of all 100s should be 100"

def test_single_critical_finding():
    findings = [create_mock_finding("security", "critical")]
    scores = compute_category_scores(findings)
    assert scores["security"] == 60, "Critical severity should deduct exactly 40"
    assert scores["ci_cd"] == 100, "Unrelated categories should stay unaffected at 100"
    assert scores["dependencies"] == 100
    
def test_multiple_criticals_clamp_at_zero():
    findings = [
        create_mock_finding("dependency", "critical"),
        create_mock_finding("dependency", "critical"),
        create_mock_finding("dependency", "critical")
    ]
    scores = compute_category_scores(findings)
    assert scores["dependencies"] == 0, "Score should clamp at 0 and never go negative"

def test_overall_score_averages_all_categories():
    scores = {
        "ci_cd": 100,
        "dependencies": 50,
        "security": 100,
        "issues": 100,
        "pull_requests": 100,
        "code_quality": 100
    }
    # Average is (100*5 + 50) / 6 = 550 / 6 = 91.666 -> rounded to 92
    overall = compute_overall_score(scores)
    assert overall == 92, "Overall score should average all 6 provided categories and round to closest integer"

def test_unmapped_category_is_ignored():
    findings = [
        create_mock_finding("some_unknown_category", "critical"),
        # 'repository_activity' should map to 'ci_cd' and deduct 20 for high
        create_mock_finding("repository_activity", "high") 
    ]
    scores = compute_category_scores(findings)
    assert scores["ci_cd"] == 80, "repository_activity should be mapped to ci_cd"
    assert all(scores[cat] == 100 for cat in scores if cat != "ci_cd"), "Unmapped categories must be silently ignored"

def test_compute_overall_empty():
    assert compute_overall_score({}) == 100, "Empty category scores dict should return 100"
