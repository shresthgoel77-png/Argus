import sys
import uuid
import asyncio

# Setup path so importing app works
sys.path.append('.')

def seed():
    import importlib
    import pkgutil
    import app.models
    for _, name, _ in pkgutil.iter_modules(app.models.__path__):
        importlib.import_module(f'app.models.{name}')
        
    from app.db.session import SessionLocal
    from app.models.user import User
    from app.models.repository import Repository
    from app.models.notification import Notification
    from app.models.finding import Finding
    from app.models.repository_health_snapshot import RepositoryHealthSnapshot
    
    db = SessionLocal()
    user = db.query(User).first()
    if not user:
        user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            auth_provider="github",
            external_auth_id="12345"
        )
        db.add(user)
        db.commit()
        
    from app.models.github_connection import GitHubConnection
    conn = db.query(GitHubConnection).first()
    if not conn:
        conn = GitHubConnection(
            id=uuid.uuid4(),
            user_id=user.id,
            installation_id=98765,
            account_login="testuser",
            account_type="User"
        )
        db.add(conn)
        db.commit()
        
    repo = db.query(Repository).first()
    if not repo:
        repo = Repository(
            id=uuid.uuid4(),
            connection_id=conn.id,
            github_repo_id=112233,
            full_name="testuser/testrepo",
            private=False
        )
        db.add(repo)
        db.commit()
        
    # We will create one finding and one health snapshot mock references if they don't exist
    finding = db.query(Finding).first()
    if not finding:
        finding = Finding(
            id=uuid.uuid4(),
            repository_id=repo.id,
            category="dependency",
            type="outdated",
            title="Seed Critical Finding",
            severity="critical",
            status="open",
            description="A critical seeded finding.",
            source="dependabot",
            evidence={"package":"lodash", "version":"4.17.15"}
        )
        db.add(finding)
        db.commit()
        
    snapshot = db.query(RepositoryHealthSnapshot).first()
    if not snapshot:
        snapshot = RepositoryHealthSnapshot(
            id=uuid.uuid4(),
            repository_id=repo.id,
            overall_score=45,
            category_scores={"security": 50, "activity": 40},
            reasons=["Low activity"]
        )
        db.add(snapshot)
        db.commit()
        
    db.commit()

    print("Seeding notifications...")
    # Seed finding notification
    notif1 = Notification(
        user_id=user.id,
        repository_id=repo.id,
        notification_type='finding_created',
        severity='critical',
        title='Critical finding created',
        message='A new critical finding has been created in your repo.',
        reference_type='finding',
        reference_id=str(finding.id)
    )
    # Seed health drop notification
    notif2 = Notification(
        user_id=user.id,
        repository_id=repo.id,
        notification_type='health_score_dropped',
        severity='warning',
        title='Health score dropped',
        message='Your repository health score dropped significantly.',
        reference_type='health_snapshot',
        reference_id=str(snapshot.id)
    )
    
    # Try adding custom unknown type to test mapping
    # Note: CheckConstraint allows only 'finding', 'health_snapshot'
    # So we can only seed an unknown type if the database allows it or we drop constraint, or we can just mock it in tests.
    
    db.add(notif1)
    db.add(notif2)
    db.commit()
    print("Database seeded with notifications!")

if __name__ == "__main__":
    seed()
