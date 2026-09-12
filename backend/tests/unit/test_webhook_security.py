import hmac
import hashlib
import pytest
from pydantic import SecretStr
from app.integrations.github.webhook_security import verify_signature

@pytest.fixture
def mock_settings(monkeypatch):
    monkeypatch.setattr(
        "app.integrations.github.webhook_security.settings.github_app_webhook_secret",
        SecretStr("test_secret")
    )

def test_verify_signature_correct(mock_settings):
    payload = b'{"action":"opened","issue":{"number":1}}'
    secret = b"test_secret"
    digest = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    signature_header = f"sha256={digest}"
    
    assert verify_signature(payload, signature_header) is True

def test_verify_signature_wrong_secret(mock_settings):
    payload = b'{"action":"opened","issue":{"number":1}}'
    wrong_secret = b"wrong_secret"
    digest = hmac.new(wrong_secret, payload, hashlib.sha256).hexdigest()
    signature_header = f"sha256={digest}"
    
    assert verify_signature(payload, signature_header) is False

def test_verify_signature_tampered_body(mock_settings):
    payload = b'{"action":"opened","issue":{"number":1}}'
    secret = b"test_secret"
    digest = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    signature_header = f"sha256={digest}"
    
    tampered_payload = b'{"action":"closed","issue":{"number":1}}'
    
    assert verify_signature(tampered_payload, signature_header) is False

def test_verify_signature_missing_header(mock_settings):
    payload = b'{"action":"opened","issue":{"number":1}}'
    
    assert verify_signature(payload, None) is False

def test_verify_signature_malformed_header(mock_settings):
    payload = b'{"action":"opened","issue":{"number":1}}'
    secret = b"test_secret"
    digest = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    
    # Missing 'sha256=' prefix
    signature_header = digest
    assert verify_signature(payload, signature_header) is False
    
    # Different prefix
    signature_header_sha1 = f"sha1={digest}"
    assert verify_signature(payload, signature_header_sha1) is False
