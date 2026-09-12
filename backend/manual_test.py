import json
import hmac
import hashlib
from uuid import uuid4
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.github_event import GitHubEvent
from app.core.config import settings

def _sign_payload(payload_bytes: bytes) -> str:
    secret_bytes = settings.github_app_webhook_secret.get_secret_value().encode('utf-8')
    mac = hmac.new(secret_bytes, payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={mac}"

def run_manual_test():
    with TestClient(app) as client:
        db = SessionLocal()
        try:
            payload = {"action": "manual_test"}
            body_bytes = json.dumps(payload).encode("utf-8")
            valid_sig = _sign_payload(body_bytes)
            
            print("--- Manual Verification ---")
            
            # 1. Corrupted signature
            del_id_invalid = str(uuid4())
            headers1 = {
                "x-github-event": "push",
                "x-github-delivery": del_id_invalid,
                "x-hub-signature-256": "sha256=deadbeefdeadbeef"
            }
            resp1 = client.post("/api/v1/webhooks/github", content=body_bytes, headers=headers1)
            print(f"Corrupt Signature -> Status: {resp1.status_code}")
            row_exists1 = db.query(GitHubEvent).filter_by(delivery_id=del_id_invalid).first() is not None
            print(f"Zero Rows Persisted: {not row_exists1}")
            
            # 2. Valid signature
            del_id_valid = str(uuid4())
            headers2 = {
                "x-github-event": "push",
                "x-github-delivery": del_id_valid,
                "x-hub-signature-256": valid_sig
            }
            resp2 = client.post("/api/v1/webhooks/github", content=body_bytes, headers=headers2)
            print(f"Valid Signature -> Status: {resp2.status_code}")
            row_exists2 = db.query(GitHubEvent).filter_by(delivery_id=del_id_valid).first() is not None
            print(f"Persisted GitHubEvent: {row_exists2}")
            
        finally:
            db.close()

if __name__ == "__main__":
    run_manual_test()
