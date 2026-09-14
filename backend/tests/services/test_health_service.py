import uuid
import pytest
from app.models.finding import Finding
from app.models.repository_health_snapshot import RepositoryHealthSnapshot
from app.services.health_service import generate_reasons, compute_and_persist_health

class MockSession:
    def __init__(self):
        self.added = []
    def add(self, obj):
        self.added.append(obj)
    def commit(self):
        pass
    def refresh(self, obj):
        pass


def test_generate_reasons_first_snapshot():
    reasons = generate_reasons(None, {"security": 100}, 100, [])
    assert reasons == ["Initial health score computed."]

def test_generate_reasons_no_change():
    prev = RepositoryHealthSnapshot(category_scores={"security": 100, "ci_cd": 100})
    reasons = generate_reasons(prev, {"security": 100, "ci_cd": 100}, 100, [])
    assert reasons == ["No change since last check."]

def test_generate_reasons_improvement():
    prev = RepositoryHealthSnapshot(category_scores={"security": 60})
    reasons = generate_reasons(prev, {"security": 100}, 100, [])
    assert len(reasons) == 1
    assert "improved by 40 points" in reasons[0]
    assert "Security" in reasons[0]

def test_generate_reasons_drop():
    prev = RepositoryHealthSnapshot(category_scores={"security": 100})
    f = Finding(category="security", severity="critical", type="sql_injection")
    reasons = generate_reasons(prev, {"security": 60}, 60, [f])
    assert len(reasons) == 1
    assert "dropped by 40 points" in reasons[0]
    assert "Security" in reasons[0]
    assert "sql_injection" in reasons[0]
    assert "critical" in reasons[0]

def test_compute_and_persist_health_zero_findings(monkeypatch):
    monkeypatch.setattr("app.services.health_service.get_all_open_findings_for_repository", lambda db, repo: [])
    monkeypatch.setattr("app.services.health_service.get_latest_snapshot", lambda db, repo: None)
    
    db = MockSession()
    repo_id = uuid.uuid4()
    
    snapshot = compute_and_persist_health(db, repo_id)
    assert snapshot.overall_score == 100
    assert snapshot.reasons == ["Initial health score computed."]
    assert snapshot in db.added


def test_compute_and_persist_health_critical_finding(monkeypatch):
    f = Finding(category="security", severity="critical", type="cve-1234")
    monkeypatch.setattr("app.services.health_service.get_all_open_findings_for_repository", lambda db, repo: [f])
    
    prev = RepositoryHealthSnapshot(category_scores={"security": 100, "ci_cd": 100, "dependencies": 100, "issues": 100, "pull_requests": 100, "code_quality": 100})
    monkeypatch.setattr("app.services.health_service.get_latest_snapshot", lambda db, repo: prev)
    
    db = MockSession()
    repo_id = uuid.uuid4()
    
    snapshot = compute_and_persist_health(db, repo_id)
    assert snapshot.overall_score < 100
    assert any("dropped" in r for r in snapshot.reasons)
    assert snapshot in db.added


def test_compute_and_persist_health_resolved_finding(monkeypatch):
    monkeypatch.setattr("app.services.health_service.get_all_open_findings_for_repository", lambda db, repo: [])
    
    prev = RepositoryHealthSnapshot(category_scores={"security": 60, "ci_cd": 100, "dependencies": 100, "issues": 100, "pull_requests": 100, "code_quality": 100})
    monkeypatch.setattr("app.services.health_service.get_latest_snapshot", lambda db, repo: prev)
    
    db = MockSession()
    repo_id = uuid.uuid4()
    
    snapshot = compute_and_persist_health(db, repo_id)
    assert snapshot.overall_score > 60
    assert any("improved" in r for r in snapshot.reasons)


def test_compute_and_persist_health_no_changes(monkeypatch):
    f = Finding(category="security", severity="critical", type="cve-1234")
    monkeypatch.setattr("app.services.health_service.get_all_open_findings_for_repository", lambda db, repo: [f])
    
    prev = RepositoryHealthSnapshot(category_scores={"security": 60, "ci_cd": 100, "dependencies": 100, "issues": 100, "pull_requests": 100, "code_quality": 100})
    monkeypatch.setattr("app.services.health_service.get_latest_snapshot", lambda db, repo: prev)
    
    db = MockSession()
    repo_id = uuid.uuid4()
    
    snapshot = compute_and_persist_health(db, repo_id)
    assert snapshot.overall_score == int(round((60 + 100*5) / 6))
    assert snapshot.reasons == ["No change since last check."]
