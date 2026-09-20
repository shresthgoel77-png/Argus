import uuid
from datetime import datetime
from app.models.repository_health_snapshot import RepositoryHealthSnapshot
from app.models.finding import Finding
from app.services.trend_service import get_health_trend, get_finding_velocity
from app.services.health_score_service import HEALTH_CATEGORIES

class MockQuery:
    def __init__(self, db_parent):
        self.db_parent = db_parent
        self.is_snapshot = False

    def filter(self, *args, **kwargs):
        self.filters = args
        return self
        
    def order_by(self, *args, **kwargs):
        return self
        
    def group_by(self, *args, **kwargs):
        return self
        
    def all(self):
        if self.is_snapshot:
            return self.db_parent.snapshot_results
            
        for f in getattr(self, 'filters', []):
            if "resolved_at" in str(f):
                return self.db_parent.resolved_results
        return self.db_parent.detected_results

class MockSession:
    def __init__(self, snapshot_results=None, detected_results=None, resolved_results=None):
        self.snapshot_results = snapshot_results or []
        self.detected_results = detected_results or []
        self.resolved_results = resolved_results or []

    def query(self, *args):
        mq = MockQuery(self)
        if args and args[0] is RepositoryHealthSnapshot:
            mq.is_snapshot = True
        return mq

def test_get_health_trend_no_history():
    db = MockSession(snapshot_results=[])
    overall, cats = get_health_trend(db, uuid.uuid4())
    assert overall == 0
    for c in HEALTH_CATEGORIES:
        assert cats[c] == 0

def test_get_health_trend_one_snapshot():
    s1 = RepositoryHealthSnapshot(overall_score=80, category_scores={"security": 80})
    db = MockSession(snapshot_results=[s1])
    overall, cats = get_health_trend(db, uuid.uuid4())
    assert overall == 0
    for c in HEALTH_CATEGORIES:
        assert cats[c] == 0

def test_get_health_trend_improving():
    s1 = RepositoryHealthSnapshot(overall_score=60, category_scores={"security": 60, "ci_cd": 100})
    s2 = RepositoryHealthSnapshot(overall_score=90, category_scores={"security": 100, "ci_cd": 80})
    db = MockSession(snapshot_results=[s1, s2])
    overall, cats = get_health_trend(db, uuid.uuid4())
    
    assert overall == 30
    assert cats["security"] == 40
    assert cats["ci_cd"] == -20
    # Other categories default to 100->100 => 0
    assert cats["issues"] == 0

def test_get_finding_velocity():
    detected = [("security", 5), ("ci", 2)]
    resolved = [("security", 3)]
    
    db = MockSession(detected_results=detected, resolved_results=resolved)
    v = get_finding_velocity(db, uuid.uuid4())
    
    # "security" Maps to "security", "ci" maps to "ci_cd"
    assert v["security"]["detected"] == 5
    assert v["security"]["resolved"] == 3
    
    assert v["ci_cd"]["detected"] == 2
    assert v["ci_cd"]["resolved"] == 0
    
    assert v["issues"]["detected"] == 0
    assert v["issues"]["resolved"] == 0
