import asyncio
import uuid
from httpx import AsyncClient, ASGITransport
import sys
import json
import os

# Ensure backend root is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.models.notification import Notification as NotificationModel
from app.auth.dependencies import get_current_user
from app.db.base_class import Base


def setup_db():
    from sqlalchemy import create_engine
    # create in-memory sqlite for isolation
    engine = create_engine("sqlite:///./manual_test.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return engine

async def main():
    engine = setup_db()
    
    # We will override the session maker to use our isolated DB
    from sqlalchemy.orm import sessionmaker
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    db = TestingSessionLocal()
    
    # Create User A and User B
    user_a = User(id=uuid.uuid4(), email="user_a@test.com", display_name="User A", auth_provider="development", external_auth_id="ua")
    user_b = User(id=uuid.uuid4(), email="user_b@test.com", display_name="User B", auth_provider="development", external_auth_id="ub")
    db.add_all([user_a, user_b])
    db.commit()
    
    # Provision 3 notifications for User A
    n1 = NotificationModel(id=uuid.uuid4(), user_id=user_a.id, notification_type="finding_created", severity="high", title="A1", message="A1 msg", reference_type="finding", reference_id="1")
    n2 = NotificationModel(id=uuid.uuid4(), user_id=user_a.id, notification_type="health_score_dropped", severity="low", title="A2", message="A2 msg", reference_type="health_snapshot", reference_id="2")
    n3 = NotificationModel(id=uuid.uuid4(), user_id=user_a.id, notification_type="finding_created", severity="high", title="A3", message="A3 msg", reference_type="finding", reference_id="3")
    
    # Provision 1 notification for User B
    n4 = NotificationModel(id=uuid.uuid4(), user_id=user_b.id, notification_type="finding_created", severity="low", title="B1", message="B1 msg", reference_type="finding", reference_id="4")
    db.add_all([n1, n2, n3, n4])
    db.commit()
    
    print("Database seeded.")
    
    def override_get_db():
        try:
            db_sess = TestingSessionLocal()
            yield db_sess
        finally:
            db_sess.close()
            
    app.dependency_overrides[get_current_user] = lambda: user_a
    from app.db.session import get_db
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        
        print("\n--- 1. User A lists notifications ---")
        app.dependency_overrides[get_current_user] = lambda: user_a
        res = await client.get("/api/v1/notifications?limit=2")
        print(f"Status: {res.status_code}")
        data = res.json()
        print(f"Items returned (limit 2): {len(data)}")
        if data:
            print("Response Body (first item):", json.dumps(data[0], indent=2))
        
        print("\n--- 2. User B lists notifications (should not see User A's) ---")
        app.dependency_overrides[get_current_user] = lambda: user_b
        res = await client.get("/api/v1/notifications")
        print(f"Status: {res.status_code}")
        data = res.json()
        print(f"Items returned: {len(data)}, Titles: {[d['title'] for d in data]}")
        
        print("\n--- 3. User A checks unread count ---")
        app.dependency_overrides[get_current_user] = lambda: user_a
        res = await client.get("/api/v1/notifications/unread-count")
        print(f"Status: {res.status_code}")
        print("Response Body:", res.json())
        
        print("\n--- 4. User A marks one notification read ---")
        res = await client.post(f"/api/v1/notifications/{n1.id}/read")
        print(f"Status (n1 read): {res.status_code}")
        print("Response Body:", res.json())
        
        print("\n--- 5. User A checks unread count again ---")
        res = await client.get("/api/v1/notifications/unread-count")
        print(f"Status: {res.status_code}")
        print("Response Body:", res.json())
        
        print("\n--- 6. User A marks all remaining read ---")
        res = await client.post("/api/v1/notifications/read-all")
        print(f"Status: {res.status_code}")
        print("Response Body:", res.json())
        
        print("\n--- 7. User A checks unread count after marking all read ---")
        res = await client.get("/api/v1/notifications/unread-count")
        print("Response Body:", res.json())
        
        print("\n--- 8. User B attempts to mark User A's notification as read ---")
        app.dependency_overrides[get_current_user] = lambda: user_b
        res = await client.post(f"/api/v1/notifications/{n2.id}/read")
        print(f"Targeting ID: {n2.id}")
        print(f"Status: {res.status_code}")
        print("Response Body:", res.json())

if __name__ == "__main__":
    asyncio.run(main())
