from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Incident
import os

db_url = os.getenv("DATABASE_URL", "sqlite:///./incidents.db")
engine = create_engine(db_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def main():
    db = SessionLocal()
    open_incidents = db.query(Incident).filter(Incident.status != "resolved").all()
    for inc in open_incidents:
        inc.status = "resolved"
        print(f"Resolved incident {inc.id}")
    db.commit()
    db.close()
    print("Database cleared of open incidents.")

if __name__ == "__main__":
    main()
