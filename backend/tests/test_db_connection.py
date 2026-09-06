from sqlalchemy import text
from app.db.session import SessionLocal

def test_connection():
    try:
        db = SessionLocal()
        result = db.execute(text("SELECT 1"))
        print(f"Connection successful: SELECT 1 returned {result.scalar()}")
    except Exception as e:
        print(f"Connection failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_connection()
