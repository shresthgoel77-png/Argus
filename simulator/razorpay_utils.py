import hashlib
import hmac
import time
from uuid import uuid4


def build_test_payment_event(event_type="payment.captured") -> dict:
    # Simplified test-mode simulation for demo purposes, not literal Razorpay API-response parity.
    return {
        "entity": "event",
        "account_id": "acc_test_demo",
        "event": event_type,
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": f"pay_test_{uuid4().hex[:14]}",
                    "amount": 50000,
                    "currency": "INR",
                    "status": "captured",
                }
            }
        },
        "created_at": int(time.time()),
        "id": f"evt_test_{uuid4().hex[:14]}",
    }


def sign_payload(secret: str, raw_body: bytes) -> str:
    return hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()


def verify_signature(secret: str, raw_body: bytes, signature_header: str | None) -> bool:
    if signature_header is None:
        return False
    computed = sign_payload(secret, raw_body)
    return hmac.compare_digest(computed, signature_header)