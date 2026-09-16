import pytest
from app.core.encryption import encrypt_secret, decrypt_secret, SecretDecryptionError
from app.core.config import Settings
import os

def test_encryption_round_trip():
    # Valid round-trip text
    plaintext = "super_secret_ai_key"
    ciphertext = encrypt_secret(plaintext)
    
    # Must not contain plaintext
    assert plaintext not in ciphertext
    assert plaintext != ciphertext
    
    # Successful round-trip
    decrypted = decrypt_secret(ciphertext)
    assert decrypted == plaintext

def test_decryption_tampered_token():
    plaintext = "super_secret_ai_key"
    ciphertext = encrypt_secret(plaintext)
    
    tampered_ciphertext = ciphertext[:-4] + "AAAA"
    
    with pytest.raises(SecretDecryptionError):
        decrypt_secret(tampered_ciphertext)

def test_decryption_garbage_token():
    with pytest.raises(SecretDecryptionError):
        decrypt_secret("this is completely invalid garbage")

def test_settings_fails_when_key_missing(monkeypatch):
    monkeypatch.delenv("AI_CREDENTIAL_ENCRYPTION_KEY", raising=False)
    # The application initialization must fail closed
    with pytest.raises(ValueError, match="1 validation error for Settings"):
        Settings(_env_file=None)

def test_settings_fails_when_key_malformed(monkeypatch):
    monkeypatch.setenv("AI_CREDENTIAL_ENCRYPTION_KEY", "invalid_format_key")
    with pytest.raises(ValueError, match="must be a valid Fernet key"):
        Settings(_env_file=None)
