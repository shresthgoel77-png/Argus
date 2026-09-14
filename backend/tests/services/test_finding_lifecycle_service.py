import pytest
from datetime import datetime
from app.models.finding import Finding
from app.services.finding_lifecycle_service import (
    InvalidFindingTransition,
    acknowledge_finding,
    resolve_finding,
    ignore_finding,
    reopen_finding,
    auto_resolve_finding,
)

class MockSession:
    def commit(self):
        pass
    def refresh(self, obj):
        pass

@pytest.fixture
def db():
    return MockSession()

def create_finding(status: str, resolved_at=None, resolution_source=None, acknowledged_at=None) -> Finding:
    f = Finding()
    f.status = status
    f.resolved_at = resolved_at
    f.resolution_source = resolution_source
    f.acknowledged_at = acknowledged_at
    return f

def test_acknowledge_finding_valid_transitions(db):
    for status in ["open"]:
        f = create_finding(status)
        res = acknowledge_finding(db, f)
        assert res.status == "acknowledged"
        assert res.acknowledged_at is not None

def test_acknowledge_finding_invalid_transitions(db):
    for status in ["acknowledged", "resolved", "ignored"]:
        f = create_finding(status)
        with pytest.raises(InvalidFindingTransition):
            acknowledge_finding(db, f)

def test_resolve_finding_valid_transitions(db):
    for status in ["open", "acknowledged"]:
        f = create_finding(status)
        res = resolve_finding(db, f, source="manual")
        assert res.status == "resolved"
        assert res.resolved_at is not None
        assert res.resolution_source == "manual"

def test_resolve_finding_no_op(db):
    dt = datetime(2020, 1, 1)
    f = create_finding("resolved", resolved_at=dt, resolution_source="old_source")
    res = resolve_finding(db, f, source="new_source")
    
    assert res.status == "resolved"
    assert res.resolved_at == dt
    assert res.resolution_source == "old_source"

def test_resolve_finding_invalid_transitions(db):
    for status in ["ignored"]:
        f = create_finding(status)
        with pytest.raises(InvalidFindingTransition):
            resolve_finding(db, f)

def test_ignore_finding_valid_transitions(db):
    for status in ["open", "acknowledged"]:
        f = create_finding(status)
        res = ignore_finding(db, f)
        assert res.status == "ignored"
        assert getattr(res, "resolved_at", None) is None
        assert getattr(res, "resolution_source", None) is None

def test_ignore_finding_no_op(db):
    f = create_finding("ignored")
    res = ignore_finding(db, f)
    assert res.status == "ignored"

def test_ignore_finding_invalid_transitions(db):
    for status in ["resolved"]:
        f = create_finding(status)
        with pytest.raises(InvalidFindingTransition):
            ignore_finding(db, f)

def test_reopen_finding_valid_transitions(db):
    for status in ["resolved", "ignored", "acknowledged"]:
        dt = datetime(2020, 1, 1)
        f = create_finding(status, resolved_at=dt, resolution_source="test", acknowledged_at=dt)
        res = reopen_finding(db, f)
        
        assert res.status == "open"
        assert getattr(res, "resolved_at", None) is None
        assert getattr(res, "resolution_source", None) is None
        assert getattr(res, "acknowledged_at", None) is None

def test_reopen_finding_no_op(db):
    f = create_finding("open")
    res = reopen_finding(db, f)
    assert res.status == "open"

def test_auto_resolve_finding_valid_transitions(db):
    for status in ["open", "acknowledged"]:
        f = create_finding(status)
        res = auto_resolve_finding(db, f)
        
        assert res.status == "resolved"
        assert res.resolved_at is not None
        assert res.resolution_source == "auto"

def test_auto_resolve_finding_no_op(db):
    # silently no-ops from ignored or resolved
    dt = datetime(2020, 1, 1)
    
    f1 = create_finding("ignored", resolution_source="tester")
    res1 = auto_resolve_finding(db, f1)
    assert res1.status == "ignored"
    assert res1.resolution_source == "tester"
    
    f2 = create_finding("resolved", resolved_at=dt, resolution_source="admin")
    res2 = auto_resolve_finding(db, f2)
    assert res2.status == "resolved"
    assert res2.resolved_at == dt
    assert res2.resolution_source == "admin"
