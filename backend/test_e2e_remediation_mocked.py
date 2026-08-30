import sys, datetime, requests
import os
os.environ["DATABASE_URL"] = "sqlite:///./reliability.db"

from app.db import SessionLocal
from app.models import Incident, RemediationAction, Evidence

db = SessionLocal()

# 1. Create Incident
inc = Incident(
    type="high_latency",
    service="simulator",
    severity="high",
    timestamp=datetime.datetime.utcnow(),
    trigger="high_latency_threshold_exceeded",
    status="rca_complete",
    initial_metrics={"value": 1500}
)
db.add(inc)
db.commit()
db.refresh(inc)
incident_id = inc.id
print(f"Created incident {incident_id}")

# 2. Create RCA Evidence
ev = Evidence(
    incident_id=incident_id,
    category="ai_rca",
    content={
        "recommended_remediation": {
            "action_type": "rollback_deployment",
            "params": {}
        }
    }
)
db.add(ev)
db.commit()

BACKEND_URL = "http://localhost:8000"

# 3. Propose Remediation
print(f"Triggering Remediation Proposal for incident {incident_id}...")
resp = requests.post(f"{BACKEND_URL}/remediation/propose/{incident_id}")
if resp.status_code != 200:
    print(f"Error {resp.status_code}: {resp.text}")
resp.raise_for_status()
data = resp.json()
action_id = data.get("id")
print(f"Proposed Remediation ID: {action_id} | Type: {data.get('action_type')} | Status: {data.get('status')}")

# Verify it was written to the DB properly
action = db.query(RemediationAction).filter(RemediationAction.id == action_id).first()
print(f"DB Action: Type={action.action_type}, PolicyLevel={action.risk_level}")

# 4. Approve
print(f"Approving Remediation ID: {action_id}...")
resp = requests.post(f"{BACKEND_URL}/remediation/{action_id}/approve", json={"approved_by": "test-e2e-user"})
resp.raise_for_status()
print("Approval successful!")

# 5. Reject (should be 409)
print(f"Attempting to reject already approved Remediation ID: {action_id}...")
resp = requests.post(f"{BACKEND_URL}/remediation/{action_id}/reject", json={"rejected_by": "test-e2e-user"})
if resp.status_code == 409:
    print("Correctly received 409 Conflict for double-reject!")
else:
    print(f"Failed! Received {resp.status_code}")

print("--- E2E MOCKED-FLOW VALIDATION COMPLETE ---")
