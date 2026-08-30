import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import Base, engine, SessionLocal
from app.models import Incident, Evidence

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_get_evidence_returns_404_for_unknown_incident():
    response = client.get("/incidents/999/evidence")
    assert response.status_code == 404
    assert response.json()["detail"] == "Incident not found"

def test_get_evidence_returns_list_for_existing_incident():
    db = SessionLocal()
    incident = Incident(type="cpu_spike", service="test-service", status="open")
    db.add(incident)
    db.commit()
    db.refresh(incident)

    ev1 = Evidence(
        incident_id=incident.id, 
        category="metrics_facts", 
        content={"key": "value"}
    )
    db.add(ev1)
    db.commit()

    response = client.get(f"/incidents/{incident.id}/evidence")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["category"] == "metrics_facts"
    assert data[0]["content"] == {"key": "value"}
