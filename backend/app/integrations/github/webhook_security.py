import hmac
import hashlib
from app.core.config import settings

def verify_signature(payload_body: bytes, signature_header: str | None) -> bool:
    """
    Verifies that a webhook request actually came from GitHub using the shared secret.
    
    Args:
        payload_body: The raw bytes of the request body.
        signature_header: The 'x-hub-signature-256' header from the request.
        
    Returns:
        True if the signature is valid, False otherwise.
    """
    if signature_header is None:
        return False
        
    if not signature_header.startswith("sha256="):
        return False
        
    header_digest = signature_header[7:]  # Strip the 'sha256=' prefix
    
    secret_bytes = settings.github_app_webhook_secret.get_secret_value().encode('utf-8')
    
    expected_hmac = hmac.new(
        secret_bytes,
        payload_body,
        hashlib.sha256
    )
    
    expected_digest = expected_hmac.hexdigest()
    
    return hmac.compare_digest(header_digest, expected_digest)
