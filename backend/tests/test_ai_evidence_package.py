import os
import datetime
import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_incidents_ai.db"

from app.db import Base, SessionLocal, engine
from app.models import Incident, Evidence
from app.ai.evidence_package import build_evidence_package
from app.ai.client import call_rca_model, _clean_json_response, AIResponseParseError

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.query(Evidence).delete()
    db.query(Incident).delete()
    db.commit()
    db.close()
    yield
    db = SessionLocal()
    db.query(Evidence).delete()
    db.query(Incident).delete()
    db.commit()
    db.close()

def test_build_evidence_package_returns_correct_structure():
    db = SessionLocal()
    
    incident = Incident(
        type="high_error_rate",
        service="payment_service",
        severity="high",
        status="investigated",
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        initial_metrics={"error_rate": "15%"},
        trigger="cpu_usage_high"
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    
    evidence1 = Evidence(
        incident_id=incident.id,
        category="observed_fact",
        content={"metric": "cpu", "value": 95},
        created_at=datetime.datetime.now(datetime.timezone.utc)
    )
    evidence2 = Evidence(
        incident_id=incident.id,
        category="hypothesis",
        content={"theory": "bad_deployment"},
        created_at=datetime.datetime.now(datetime.timezone.utc)
    )
    
    db.add_all([evidence1, evidence2])
    db.commit()
    db.refresh(evidence1)
    db.refresh(evidence2)
    
    package = build_evidence_package(incident, db)
    
    # Asserting Incident
    assert "incident" in package
    assert package["incident"]["id"] == incident.id
    assert package["incident"]["type"] == "high_error_rate"
    
    # Asserting Evidence
    assert "evidence" in package
    assert len(package["evidence"]) == 2
    
    ev_list = package["evidence"]
    assert ev_list[0]["id"] == str(evidence1.id)
    assert ev_list[0]["content"]["metric"] == "cpu"
    
    assert ev_list[1]["id"] == str(evidence2.id)
    assert ev_list[1]["category"] == "hypothesis"
    db.close()

def test_build_evidence_package_zero_evidence():
    db = SessionLocal()
    incident = Incident(
        type="timeout",
        service="auth",
        severity="low",
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    
    package = build_evidence_package(incident, db)
    assert "evidence" in package
    assert package["evidence"] == []
    db.close()

def test_clean_json_response_strips_markdown():
    wrapped = "```json\n{\"foo\": \"bar\"}\n```"
    cleaned = _clean_json_response(wrapped)
    assert cleaned == "{\"foo\": \"bar\"}"
    
    naked = "{\"foo\": \"bar\"}"
    assert _clean_json_response(naked) == naked
    
    code = "```\n{\"foo\": \"bar\"}\n```"
    assert _clean_json_response(code) == "{\"foo\": \"bar\"}"

@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="requires valid GEMINI_API_KEY")
def test_call_rca_model_returns_parseable_json():
    # Construct a minimal realistic package
    package = {
        "incident": {
            "id": 1,
            "type": "CrashLoopBackOff",
            "service": "frontend",
            "severity": "high",
            "timestamp": "2026-01-01T10:00:00Z"
        },
        "evidence": [
            {
                "id": "100",
                "category": "observed_fact",
                "content": {"log": "OOMKilled process", "source": "kubectl"},
                "created_at": "2026-01-01T10:05:00Z"
            }
        ]
    }
    
    response = call_rca_model(package)
    
    # Only loose structural check, Prompt 2 validates exact schema
    assert isinstance(response, dict)
    assert "summary" in response
    assert "confidence" in response
    assert "root_cause" in response
    assert "supporting_evidence" in response
    assert "recommended_remediation" in response
