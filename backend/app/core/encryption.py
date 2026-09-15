from cryptography.fernet import Fernet
from app.core.config import settings

class SecretDecryptionError(Exception):
    """Raised when an encrypted secret fails to decrypt or is tampered with."""
    pass

_fernet_instance = Fernet(settings.ai_credential_encryption_key.get_secret_value())

def encrypt_secret(plaintext: str) -> str:
    """
    Encrypts a plaintext secret into a URL-safe base64-encoded string.
    """
    return _fernet_instance.encrypt(plaintext.encode("utf-8")).decode("utf-8")

def decrypt_secret(token: str) -> str:
    """
    Decrypts a URL-safe base64-encoded token back into the original plaintext.
    Raises SecretDecryptionError on failure to prevent silent errors or garbled data.
    """
    try:
        return _fernet_instance.decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception:
        raise SecretDecryptionError("Failed to decrypt the secret.")
