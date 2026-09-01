import os
import time
import httpx
import pytest
import threading

# Use SQLite for tests to avoid DB pollution; matched with Phase 3/7 patterns.
# Disable cooldown specifically for this test to ensure back-to-back idempotency.
os.environ["DATABASE_URL"] = "sqlite:///./test_incidents_e2e.db"
os.environ["COOLDOWN_SECONDS"] = "0"
os.environ["VERIFICATION_MAX_WAIT_SECONDS"] = "60"

pytestmark = pytest.mark.e2e

from fastapi.testclient import TestClient
from app.main import app
from app.db import Base, SessionLocal, engine
from app.models import Incident, Evidence, RemediationAction, VerificationResult

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.query(VerificationResult).delete()
    db.query(RemediationAction).delete()
    db.query(Evidence).delete()
    db.query(Incident).delete()
    db.commit()
    db.close()
    yield
    db = SessionLocal()
    db.query(VerificationResult).delete()
    db.query(RemediationAction).delete()
    db.query(Evidence).delete()
    db.query(Incident).delete()
    db.commit()
    db.close()

@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="requires valid GEMINI_API_KEY for real AI calls"
)
def test_golden_path(generate_traffic, SIMULATOR_URL):
    """
    End-to-end integration test of the entire SRE incident lifecycle.
    Exercises generating real traffic, detecting issues, investigating limits,
    real AI RCA, governed remediation, and verification recovery.
    """
    
    # --- 1. Clean Simulator State ---
    res_reset = httpx.post(f"{SIMULATOR_URL}/simulate/reset", timeout=5.0)
    assert res_reset.status_code == 200, f"stage 1: failed to reset simulator: {res_reset.text}"
    
    # --- 2. Initial healthy state check ---
    generate_traffic(15.0)
    res_det1 = client.post("/detection/run")
    assert res_det1.status_code == 200, "stage 2: detection run failed"
    assert len(res_det1.json()["new_incidents"]) == 0, "stage 2: expected no incidents on clean state"

    # --- 3. Trigger Bad Deployment ---
    res_bad = httpx.post(f"{SIMULATOR_URL}/simulate/bad-deployment", timeout=5.0)
    assert res_bad.status_code == 200, "stage 3: failed to trigger bad deployment"
    commit_sha = res_bad.json()["commit_sha"]
    assert commit_sha, "stage 3: failed to capture commit_sha"

    # --- 4. Generate Degraded Traffic ---
    # Need to wait enough for Prometheus scraping and 15s/1m rate windows.
    generate_traffic(15.0)

    # --- 5. Detection Pass ---
    # Retry a few times in case metrics haven't fully propped up yet
    incidents = []
    for _ in range(5):
        res_det2 = client.post("/detection/run")
        assert res_det2.status_code == 200, "stage 5: detection run failed"
        incidents = res_det2.json()["new_incidents"]
        if incidents:
            break
        generate_traffic(3.0)
        
    assert len(incidents) >= 1, f"stage 5: expected at least 1 new incident, got {len(incidents)}"
    incident = incidents[0]
    incident_id = incident["id"]
    assert incident["initial_metrics"]["value"] > 0, "stage 5: initial_metrics value should be non-zero"
    
    # --- 6. Investigation ---
    res_inv = client.post(f"/investigation/run/{incident_id}")
    assert res_inv.status_code == 200, f"stage 6: investigation failed, got {res_inv.status_code}"
    
    db = SessionLocal()
    evidence_rows = db.query(Evidence).filter(Evidence.incident_id == incident_id).all()
    categories = [e.category for e in evidence_rows]
    if "git" not in categories:
        errors = [e.content for e in evidence_rows if e.category == "collection_error"]
        print(f"DEBUG COLLECTION ERRORS: {errors}")
    assert "observed_fact" in categories, "stage 6: missing observed_fact evidence"
    assert "hypothesis" in categories, "stage 6: missing hypothesis evidence"
    
    git_ev = next((e for e in evidence_rows if e.category == "observed_fact" and e.content.get("source") == "git"), None)
    assert git_ev, "stage 6: missing git evidence"
    commits = git_ev.content.get("commits", [])
    
    commits = git_ev.content.get("commits", [])
    assert any(c.get("sha") == commit_sha for c in commits), f"stage 6: expected {commit_sha} in git evidence"
    
    ev_ids = [str(e.id) for e in evidence_rows]
    db.close()
    
    # --- 7. AI Root Cause Analysis ---
    res_rca = client.post(f"/ai/rca/{incident_id}")
    assert res_rca.status_code == 200, f"stage 7: RCA failed, got {res_rca.status_code}: {res_rca.text}"
    rca_data = res_rca.json()["rca"]
    
    action_type = rca_data["recommended_remediation"]["action_type"]
    from app.ai.schema import ALLOWED_REMEDIATION_TYPES
    assert action_type in ALLOWED_REMEDIATION_TYPES, f"stage 7: action_type '{action_type}' not in allowlist"
    
    for ref_id in rca_data["supporting_evidence"]:
        assert str(ref_id) in ev_ids, f"stage 7: supporting_evidence ID {ref_id} not real"
        
    db = SessionLocal()
    ai_ev = db.query(Evidence).filter(Evidence.incident_id == incident_id, Evidence.category == "ai_rca").first()
    assert ai_ev, "stage 7: ai_rca evidence row not persisted"
    db.close()
    
    # --- 8. Remediation Propose ---
    res_prop = client.post(f"/remediation/propose/{incident_id}")
    assert res_prop.status_code == 200, f"stage 8: remediation propose failed, get {res_prop.text}"
    action_id = res_prop.json()["id"]
    assert res_prop.json()["status"] == "pending_approval", "stage 8: expected status pending_approval"
    
    # --- 9. Remediation Approve ---
    res_app = client.post(f"/remediation/{action_id}/approve", json={"approved_by": "golden_path_agent"})
    assert res_app.status_code == 200, "stage 9: remediation approve failed"
    assert res_app.json()["status"] == "approved", "stage 9: expected status approved"
    
    # Edge case: AI proposed an action we don't have a handler for. Skip cleanly.
    if action_type != "rollback_deployment":
        pytest.skip(f"stage 10: skipping execution/verification because action_type was {action_type}, which correctly lacks a handler in Phase 7")
        
    # --- 10. Remediation Execute ---
    res_exec = client.post(f"/remediation/{action_id}/execute")
    assert res_exec.status_code == 200, f"stage 10: remediation execute failed: {res_exec.text}"
    exec_data = res_exec.json()
    assert exec_data["action"]["status"] == "executed", f"stage 10: expected executed status, got {exec_data['action']['status']}"
    assert exec_data["result"].get("commit_sha"), "stage 10: missing commit_sha in execution result"
    
    res_state = httpx.get(f"{SIMULATOR_URL}/simulate/state")
    assert res_state.json()["bad_deployment_active"] is False, "stage 10: simulator state should not be bad_deployment_active"
    
    # --- 11 & 12. Verification Wait/Recovery (w/ background traffic) ---
    def bg_traffic():
        generate_traffic(50.0)
        
    t = threading.Thread(target=bg_traffic)
    t.start()
    
    res_ver = client.post(f"/verification/run/{incident_id}")
    t.join()
    
    assert res_ver.status_code == 200, f"stage 12: verification failed: {res_ver.text}"
    ver_data = res_ver.json()
    assert ver_data["recovered"] is True, "stage 12: expected recovered=True"
    
    db = SessionLocal()
    db_inc = db.query(Incident).filter(Incident.id == incident_id).first()
    assert db_inc.status == "resolved", f"stage 12: expected incident.status resolved, got {db_inc.status}"
    db.close()
    
    # --- 13. AI Incident Report Generation ---
    res_rep = client.get(f"/incidents/{incident_id}/report")
    assert res_rep.status_code == 200, "stage 13: report fetch failed"
    markdown = res_rep.json()["markdown"]
    
    assert rca_data["root_cause"] in markdown, "stage 13: report missing real root cause text"
    assert commit_sha in markdown, "stage 13: report missing real bad commit sha"
    
    # --- 14. Verify final incident status representation via API ---
    res_inc = client.get(f"/incidents/{incident_id}")
    assert res_inc.status_code == 200, "stage 14: incident fetch failed"
    assert res_inc.json()["status"] == "resolved", f"stage 14: expected final status resolved, got {res_inc.json()['status']}"
