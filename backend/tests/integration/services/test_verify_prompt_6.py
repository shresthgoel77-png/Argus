import uuid
from datetime import datetime, timezone
import pytest
from app.models.finding import Finding
from app.models.repository_health_snapshot import RepositoryHealthSnapshot
from app.models.notification import Notification
from app.services.health_service import compute_and_persist_health
from app.services.health_score_service import assessment_coverage, HEALTH_CATEGORY_TO_CHECK

def test_verify_end_to_end_health_drop(db_session, test_user_repository, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "health_drop_notification_threshold", 15)
    
    # Disable email sending to prevent side-effects since we just want notification row
    from app.models.notification_preference import NotificationPreference
    db_session.add(NotificationPreference(user_id=test_user_repository.connection.user_id, email_enabled=False))
    test_user_repository.monitoring_status = "success"
    test_user_repository.monitoring_checks = {
        name: {"status": "success"} for name in HEALTH_CATEGORY_TO_CHECK.values()
    }
    coverage = assessment_coverage(test_user_repository.monitoring_checks)

    db_session.query(Notification).delete()
    db_session.query(RepositoryHealthSnapshot).delete()
    db_session.query(Finding).delete()
    db_session.commit()
    
    # 1. First-ever snapshot
    snap1 = compute_and_persist_health(db_session, test_user_repository.id)
    nots1 = db_session.query(Notification).all()
    assert snap1.overall_score == 100
    assert nots1 == []
    print(f"\n1. First-ever snapshot computed.")
    print(f"   -> Notifications created: {len(nots1)} (Expected: 0)")
    
    # 2. Improvement
    snap_bad = RepositoryHealthSnapshot(repository_id=test_user_repository.id, overall_score=50, category_scores={category: 50 for category in HEALTH_CATEGORY_TO_CHECK}, coverage=coverage, computed_at=datetime.now(timezone.utc))
    db_session.add(snap_bad)
    db_session.commit()
    
    snap2 = compute_and_persist_health(db_session, test_user_repository.id)
    nots2 = db_session.query(Notification).all()
    assert snap2.overall_score == 100
    assert nots2 == []
    print(f"2. Improvement (Score went from 50 to {snap2.overall_score}).")
    print(f"   -> Notifications created: {len(nots2)} (Expected: 0)")
    
    db_session.query(Notification).delete()
    db_session.commit()
    
    # 3. Drop below threshold
    f_med = Finding(repository_id=test_user_repository.id, category="security", type="secret", title="t", description="d", severity="medium", priority="medium", source="s", status="open", evidence={})
    db_session.add(f_med)
    db_session.commit()
    
    snap3 = compute_and_persist_health(db_session, test_user_repository.id)
    nots3 = db_session.query(Notification).all()
    drop3 = 100 - snap3.overall_score
    assert 0 < drop3 < settings.health_drop_notification_threshold
    assert nots3 == []
    print(f"3. Drop below threshold (Score dropped by {drop3} points, threshold={settings.health_drop_notification_threshold}).")
    print(f"   -> Notifications created: {len(nots3)} (Expected: 0)")
    
    db_session.query(Notification).delete()
    db_session.commit()
    
    # 4. Large drop
    findings = []
    for cat in ["security", "ci", "dependency", "issue", "pull_request", "code_quality"]:
        for i in range(2):
            findings.append(Finding(repository_id=test_user_repository.id, category=cat, type=f"type{i}", title="t", description="d", severity="critical", priority="critical", source="s", status="open", evidence={}))
    db_session.add_all(findings)
    db_session.commit()
    
    db_session.add(RepositoryHealthSnapshot(repository_id=test_user_repository.id, overall_score=100, category_scores={category: 100 for category in HEALTH_CATEGORY_TO_CHECK}, coverage=coverage, computed_at=datetime.now(timezone.utc)))
    db_session.commit()
    
    snap4 = compute_and_persist_health(db_session, test_user_repository.id)
    nots4 = db_session.query(Notification).all()
    drop4 = 100 - snap4.overall_score
    assert drop4 >= settings.health_drop_notification_threshold
    assert len(nots4) == 1
    assert nots4[0].notification_type == "health_score_dropped"
    assert nots4[0].reference_id == str(snap4.id)
    print(f"4. Large drop (Score dropped by {drop4} points).")
    print(f"   -> Notifications created: {len(nots4)} (Expected: 1)")
    if len(nots4) > 0:
        n = nots4[-1]
        print(f"      - notification_type: {n.notification_type}")
        print(f"      - severity: {n.severity}")
        print(f"      - reference_type: {n.reference_type}")
        print(f"      - reference_id: {n.reference_id}")
        
    # Clear for dispatch failure
    db_session.query(Notification).delete()
    db_session.commit()
    
    # 5. Dispatch failure does not abort persistence
    import app.services.notification_dispatch_service as nds
    original_dispatch = nds.dispatch_notification
    def failing_dispatch(*args, **kwargs):
        nonlocal dispatch_called
        dispatch_called = True
        raise RuntimeError("Simulated Email API Failure or similar")
    dispatch_called = False
    monkeypatch.setattr(nds, "dispatch_notification", failing_dispatch)
    
    db_session.add(RepositoryHealthSnapshot(repository_id=test_user_repository.id, overall_score=100, category_scores={category: 100 for category in HEALTH_CATEGORY_TO_CHECK}, coverage=coverage, computed_at=datetime.now(timezone.utc)))
    db_session.commit()
    
    snap5 = compute_and_persist_health(db_session, test_user_repository.id)
    assert dispatch_called
    assert db_session.get(RepositoryHealthSnapshot, snap5.id) is not None
    print(f"5. Dispatch failure (raised RuntimeError purposely).")
    print(f"   -> Snapshot persisted with ID: {snap5.id}")
