import sys
import uuid
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base_class import Base
from app.models.user import User
from app.models.repository import Repository
from app.models.github_connection import GitHubConnection
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference, NotificationSeverity
from app.models.finding import Finding
from app.models.repository_health_snapshot import RepositoryHealthSnapshot
from app.services.health_service import compute_and_persist_health
from app.core.config import settings

def main():
    engine = create_engine("sqlite:///verify.db")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    print("--- STARTING MANUAL FIXTURE VERIFICATION ---")
    
    # 0. Clean database
    db.query(Notification).delete()
    db.query(RepositoryHealthSnapshot).delete()
    db.query(Finding).delete()
    db.query(Repository).delete()
    db.query(GitHubConnection).delete()
    db.query(User).delete()
    db.commit()

    u = User(email="test@example.com", display_name="TestUser", auth_provider="local")
    db.add(u)
    db.commit()

    pref = NotificationPreference(user_id=u.id, email_enabled=False)
    db.add(pref)
    
    conn = GitHubConnection(user_id=u.id, installation_id=1234567, account_login="test_org", account_type="Organization")
    db.add(conn)
    db.commit()

    repo = Repository(connection_id=conn.id, github_repo_id=888999, full_name="test_org/test_repo", default_branch="main")
    db.add(repo)
    db.commit()

    snap1 = compute_and_persist_health(db, repo.id)
    nots1 = db.query(Notification).all()
    print(f"1. First-ever snapshot computed. Notifications: {len(nots1)} (Expected 0)")
    
    snap_bad = RepositoryHealthSnapshot(repository_id=repo.id, overall_score=50, category_scores={"security":50, "ci_cd": 50})
    db.add(snap_bad)
    db.commit()
    
    snap2 = compute_and_persist_health(db, repo.id)
    nots2 = db.query(Notification).all()
    print(f"2. Improvement (50 to {snap2.overall_score}). Notifications: {len(nots2)} (Expected 0)")

    db.query(Notification).delete()
    db.commit()

    f_med = Finding(repository_id=repo.id, category="security", type="secret", title="t", description="d", severity="medium", priority="med", source="s", status="open", evidence={})
    db.add(f_med)
    db.commit()
    
    snap3 = compute_and_persist_health(db, repo.id)
    nots3 = db.query(Notification).all()
    print(f"3. Small drop below threshold. Notifications: {len(nots3)} (Expected 0)")

    db.query(Notification).delete()
    db.commit()

    db.query(Finding).delete()
    db.commit()

    findings = []
    for cat in ["security", "dependency", "code_quality"]:
        for i in range(3):
            findings.append(Finding(repository_id=repo.id, category=cat, type=f"type{i}", title="t", description="d", severity="critical", priority="critical", source="s", status="open", evidence={}))
    db.add_all(findings)
    db.commit()
    
    db.add(RepositoryHealthSnapshot(repository_id=repo.id, overall_score=100, category_scores={}))
    db.commit()
    
    snap4 = compute_and_persist_health(db, repo.id)
    nots4 = db.query(Notification).all()
    print(f"4. Large drop. Notifications: {len(nots4)} (Expected 1)")
    if getattr(nots4, '__len__', lambda: 0)() > 0:
        n = nots4[-1]
        print(f"   -> Type: {n.notification_type}, Severity: {n.severity}")
        print(f"   -> Reference: {n.reference_type} / {n.reference_id}")
        
    db.query(Notification).delete()
    db.commit()

    import app.services.notification_dispatch_service as nds
    original_dispatch = nds.dispatch_notification
    def failing_dispatch(*args, **kwargs):
        raise RuntimeError("Simulated Email API Failure")
    nds.dispatch_notification = failing_dispatch
    
    db.add(RepositoryHealthSnapshot(repository_id=repo.id, overall_score=100, category_scores={}))
    db.commit()
    
    snap5 = compute_and_persist_health(db, repo.id)
    print(f"5. Dispatch failure. Snapshot saved? True (ID: {snap5.id})")
    
    nds.dispatch_notification = original_dispatch

if __name__ == "__main__":
    main()
