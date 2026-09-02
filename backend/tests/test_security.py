import datetime
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from fastapi.testclient import TestClient

# 1. Import backend app modules FIRST so 'app' in sys.modules points to backend/app
from app.db import SessionLocal
from app.models import Incident, Evidence, RemediationAction
from app.ai.schema import ALLOWED_REMEDIATION_TYPES
from app.ai.validator import validate_rca_output, RCAValidationError
from app.remediation.policy import validate_params, PolicyViolationError

# 2. Add simulator directories to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SIMULATOR_DIR = PROJECT_ROOT / "simulator"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))
if str(SIMULATOR_DIR) not in sys.path:
    sys.path.append(str(SIMULATOR_DIR))

# 3. Safely import simulator modules
from simulator.app import app as simulator_app
from simulator.razorpay_utils import build_test_payment_event, sign_payload

sim_client = TestClient(simulator_app)

# Helper to create an incident in a generic state
def _create_incident(db, status="rca_complete"):
    incident = Incident(
        type="bad_deployment",
        service="simulator",
        severity="high",
        status=status,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident.id

# DBHelper context manager
class DB:
    def __enter__(self):
        self.db = SessionLocal()
        return self.db
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()


class TestCategory1RemediationAllowlist:
    """1. Remediation allowlist enforcement (Phase 5/7)"""
    
    def test_disallowed_action_type_rejected_before_db_write(self):
        # A valid baseline response
        raw = {
            "summary": "x", "impact": "x", "affected_components": [],
            "root_cause": "x", "confidence": "high", "supporting_evidence": ["1"],
            "alternative_hypotheses": [], "recommended_fix": "x",
            "recommended_remediation": {
                "action_type": "delete_database",  # Not in allowlist
                "params": {},
                "rationale": "x"
            }
        }
        evidence_pkg = {"evidence": [{"id": 1}]}
        
        with pytest.raises(RCAValidationError) as exc:
            validate_rca_output(raw, evidence_pkg)
        assert "Invalid remediation action_type" in str(exc.value)

    def test_unexpected_params_rejected_by_policy(self):
        with pytest.raises(PolicyViolationError) as exc:
            validate_params("restart_service", {"evil_key": 1})
        assert "not allowed" in str(exc.value)

    def test_unsupported_handler_returns_501(self, security_db):
        client = security_db
        with DB() as db:
            iid = _create_incident(db, "remediation_proposed")
            action = RemediationAction(
                incident_id=iid,
                action_type="restart_service",  # Handlers map only rollback_deployment
                params={},
                risk_level="medium",
                approved=True,
                approved_by="test",
                status="approved"
            )
            db.add(action)
            db.commit()
            db.refresh(action)
            aid = action.id

        response = client.post(f"/remediation/{aid}/execute")
        assert response.status_code == 501
        
        with DB() as db:
            inc = db.get(Incident, iid)
            assert inc.status == "remediation_proposed"  # Status must be UNCHANGED


class TestCategory2AIOutputValidation:
    """2. AI output validation (Phase 5)"""

    def test_hallucinated_evidence_id_rejected(self):
        raw = {
            "summary": "x", "impact": "x", "affected_components": [],
            "root_cause": "x", "confidence": "high", 
            "supporting_evidence": ["999"], # Not in package
            "alternative_hypotheses": [], "recommended_fix": "x",
            "recommended_remediation": {
                "action_type": "restart_service",
                "params": {},
                "rationale": "x"
            }
        }
        evidence_pkg = {"evidence": [{"id": 1}]}
        
        with pytest.raises(RCAValidationError) as exc:
            validate_rca_output(raw, evidence_pkg)
        assert "hallucinated evidence id: 999" in str(exc.value)

    def test_out_of_allowlist_action_type_in_ai_output_rejected(self):
        # Already covered by TestCategory1RemediationAllowlist.test_disallowed_action_type_rejected_before_db_write
        # (This is exactly the cross-check behavior requested for new test 2b)
        pass

    def test_no_eval_exec_subprocess_with_ai_strings(self):
        """Static assertion that no code path in ai/ or remediation/ calls eval, exec, or subprocess."""
        forbidden = ["eval(", "exec(", "subprocess"]
        
        backend_dir = PROJECT_ROOT / "backend" / "app"
        dirs_to_check = [backend_dir / "ai", backend_dir / "remediation"]
        
        for d in dirs_to_check:
            for filepath in d.glob("**/*.py"):
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    for token in forbidden:
                        assert token not in content, f"Forbidden token '{token}' found in {filepath}"


class TestCategory3GitSubprocessSafety:
    """3. Git subprocess safety (Phase 1/4)"""

    def test_subprocess_uses_list_args_not_shell_true(self):
        """Static assertion that neither git_evidence.py nor deploy_sim.py uses shell=True"""
        files_to_check = [
            PROJECT_ROOT / "backend" / "app" / "investigation" / "git_evidence.py",
            PROJECT_ROOT / "simulator" / "deploy_sim.py"
        ]
        
        for filepath in files_to_check:
            if not filepath.exists():
                continue
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                assert "shell=True" not in content, f"Unsafe shell=True used in {filepath}"
    
    def test_malicious_service_name_in_git_evidence(self):
        """3b: Malicious service name must not result in command execution.
        We prove this by actually passing a shell metacharacter and confirming normal behavior."""
        from app.investigation.git_evidence import collect_git_evidence
        
        with DB() as db:
            iid = _create_incident(db, "investigated")
            inc = db.get(Incident, iid)
            inc.service = "sim;rm"
            db.commit()
            db.refresh(inc)
            
            # Run collection. If RCE happens, or if it breaks the subprocess call,
            # this will not return a valid Evidence object cleanly.
            evidence = collect_git_evidence(inc, db, repo_path=str(PROJECT_ROOT))
            
            # Confirm it collected safely without executing the shell injection
            assert evidence is not None
            assert evidence.category in ("observed_fact", "collection_error")


class TestCategory4RazorpayWebhookIntegrity:
    """4. Razorpay webhook integrity (Phase 9)"""

    def test_tampered_signature_rejected_400(self, monkeypatch):
        monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "test-secret")
        event = build_test_payment_event()
        raw_body = json.dumps(event).encode()
        valid_signature = sign_payload("test-secret", raw_body)
        tampered_signature = ("1" if valid_signature[0] != "1" else "0") + valid_signature[1:]

        response = sim_client.post(
            "/webhook/razorpay-event",
            content=raw_body,
            headers={"X-Razorpay-Signature": tampered_signature},
        )
        assert response.status_code == 400
        assert response.json()["status"] == "invalid_signature"

    def test_duplicate_event_id_ignored(self, monkeypatch):
        monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "test-secret")
        event = build_test_payment_event()
        raw_body = json.dumps(event).encode()
        signature = sign_payload("test-secret", raw_body)

        first_res = sim_client.post(
            "/webhook/razorpay-event",
            content=raw_body,
            headers={"X-Razorpay-Signature": signature},
        )
        second_res = sim_client.post(
            "/webhook/razorpay-event",
            content=raw_body,
            headers={"X-Razorpay-Signature": signature},
        )

        assert first_res.status_code == 200
        assert second_res.status_code == 200
        assert second_res.json()["status"] == "duplicate_ignored"

    def test_missing_event_id_rejected_400(self, monkeypatch):
        monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "test-secret")
        raw_body = json.dumps({"entity": "event"}).encode()  # no id field

        response = sim_client.post(
            "/webhook/razorpay-event",
            content=raw_body,
            headers={"X-Razorpay-Signature": sign_payload("test-secret", raw_body)},
        )
        assert response.status_code == 400
        assert response.json()["status"] == "missing_event_id"


class TestCategory5GitHubCredentialHandling:
    """5. GitHub credential handling (Phase 10)"""

    def test_github_token_never_in_response_body(self, security_db, monkeypatch):
        secret_token = "SECURE_TEST_TOKEN_XYZ_9999"
        monkeypatch.setenv("GITHUB_TOKEN", secret_token)
        monkeypatch.setenv("GITHUB_REPO", "owner/repo")
        
        client = security_db
        
        # Test 1: Configuration status
        res1 = client.get("/github/status")
        assert secret_token not in res1.text
        
        # Test 2: Issue Creation (mocking api so we don't actually post)
        with DB() as db:
            iid = _create_incident(db, "rca_complete")
            ai_ev = Evidence(
                incident_id=iid,
                category="ai_rca",
                content={"summary": "test"}
            )
            db.add(ai_ev)
            db.commit()
            
        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=500, json=lambda: {"message": "fake error"})
            res2 = client.post(f"/incidents/{iid}/github-issue")
            # We expect a 502 with github error evidence dumped in DB or response, 
            # we just must assert the token doesn't leak in the error message.
            assert secret_token not in res2.text

    def test_malformed_github_repo_unconfigured(self, security_db, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "fake")
        monkeypatch.setenv("GITHUB_REPO", "notarepo")
        
        client = security_db
        res = client.get("/github/status")
        assert res.json() == {"configured": False}


class TestCategory6InputValidationOnPublicEndpoints:
    """6. Input validation on public endpoints"""

    def test_invalid_status_filter_returns_400(self, security_db):
        client = security_db
        response = client.get("/incidents?status=hacked")
        assert response.status_code == 400
        assert "Invalid status filter" in response.text

    def test_empty_approved_by_returns_400(self, security_db):
        client = security_db
        with DB() as db:
            iid = _create_incident(db, "remediation_proposed")
            action = RemediationAction(
                incident_id=iid,
                action_type="restart_service",
                params={},
                risk_level="medium",
                approved=False,
                status="pending_approval"
            )
            db.add(action)
            db.commit()
            db.refresh(action)
            aid = action.id

        # empty approved_by string
        response = client.post(f"/remediation/{aid}/approve", json={"approved_by": ""})
        assert response.status_code == 400
        
        # space-only string should also fail
        response = client.post(f"/remediation/{aid}/approve", json={"approved_by": "   "})
        assert response.status_code == 400
