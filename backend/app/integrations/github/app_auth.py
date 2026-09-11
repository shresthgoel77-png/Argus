"""GitHub App JWT generation and installation access token management.

This module handles two levels of authentication:

1. **App-level JWT** — A short-lived RS256-signed JWT used to prove identity
   as the GitHub App itself.  Used only to obtain installation tokens.

2. **Installation access token** — A short-lived token scoped to a specific
   GitHub App installation.  Used for all API calls against repos / orgs
   that have installed the App.

Both tokens are cached in-process to avoid unnecessary signing / API calls.
"""

from __future__ import annotations

import time
import threading
from datetime import datetime, timezone

import jwt  # PyJWT
import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.github.exceptions import GitHubAPIError

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_GITHUB_API_BASE = "https://api.github.com"
_JWT_ALGORITHM = "RS256"

# GitHub hard-limits app JWTs to 10 minutes; we use 9 min to stay safe.
_JWT_EXPIRY_SECONDS = 9 * 60  # 540 s
# Back-date `iat` by 60 s to tolerate server clock drift.
_JWT_IAT_DRIFT_SECONDS = 60
# Refresh the cached JWT when it has fewer than this many seconds left.
_JWT_REFRESH_MARGIN_SECONDS = 60

# Refresh the cached installation token 5 minutes before expiry.
_INSTALL_TOKEN_REFRESH_MARGIN_SECONDS = 5 * 60

# ---------------------------------------------------------------------------
# In-process JWT cache
# ---------------------------------------------------------------------------
_jwt_cache_lock = threading.Lock()
_cached_jwt: str | None = None
_cached_jwt_exp: float = 0.0  # Unix timestamp


def generate_app_jwt() -> str:
    """Return a cached or freshly-signed GitHub App JWT (RS256).

    The JWT is reused until 60 s before its expiry to amortise the signing
    cost across multiple calls.
    """
    global _cached_jwt, _cached_jwt_exp

    now = time.time()
    with _jwt_cache_lock:
        if _cached_jwt is not None and now < (_cached_jwt_exp - _JWT_REFRESH_MARGIN_SECONDS):
            return _cached_jwt

    # Build a new JWT outside the lock (signing is CPU-bound, not critical section)
    iat = int(now) - _JWT_IAT_DRIFT_SECONDS
    exp = int(now) + _JWT_EXPIRY_SECONDS
    payload = {
        "iat": iat,
        "exp": exp,
        "iss": settings.github_app_id,
    }

    private_key = settings.github_app_private_key.get_secret_value()
    signed_token = jwt.encode(payload, private_key, algorithm=_JWT_ALGORITHM)

    with _jwt_cache_lock:
        _cached_jwt = signed_token
        _cached_jwt_exp = float(exp)

    # SECURITY: Never log the signed JWT or private key.
    logger.info("Generated new GitHub App JWT (expires in %ds)", _JWT_EXPIRY_SECONDS)
    return signed_token


# ---------------------------------------------------------------------------
# In-process installation-token cache
# ---------------------------------------------------------------------------
# NOTE: This in-process cache is sufficient for a single backend instance.
# In a future multi-instance deployment a shared cache (e.g. Redis) would be
# needed so that every instance doesn't independently request its own token.
# This is explicitly flagged as out of scope for now.
# ---------------------------------------------------------------------------
_install_token_cache_lock = threading.Lock()
_install_token_cache: dict[int, tuple[str, float]] = {}
# Maps installation_id -> (token, expires_at_unix)


async def get_installation_access_token(installation_id: int) -> str:
    """Return a cached or freshly-obtained installation access token.

    Calls ``POST /app/installations/{id}/access_tokens`` authenticated with
    the App JWT when the cache is cold or expired.

    Args:
        installation_id: The numeric GitHub App installation ID.

    Returns:
        A short-lived installation access token string.

    Raises:
        GitHubAPIError: On any non-2xx response from GitHub.
    """
    now = time.time()
    with _install_token_cache_lock:
        cached = _install_token_cache.get(installation_id)
        if cached is not None:
            token, expires_at = cached
            if now < (expires_at - _INSTALL_TOKEN_REFRESH_MARGIN_SECONDS):
                return token

    # Fetch a fresh token from GitHub.
    app_jwt = generate_app_jwt()

    url = f"{_GITHUB_API_BASE}/app/installations/{installation_id}/access_tokens"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        # SECURITY: Authorization header is intentionally NOT logged.
        "Authorization": f"Bearer {app_jwt}",
    }

    async with httpx.AsyncClient() as http:
        response = await http.post(url, headers=headers)

    if response.status_code < 200 or response.status_code >= 300:
        raise GitHubAPIError.from_response(response)

    data = response.json()
    new_token: str = data["token"]
    expires_at_str: str = data["expires_at"]  # ISO-8601 e.g. "2024-01-01T01:00:00Z"
    expires_at_unix = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00")).replace(
        tzinfo=timezone.utc
    ).timestamp()

    with _install_token_cache_lock:
        _install_token_cache[installation_id] = (new_token, expires_at_unix)

    # SECURITY: Never log the token value itself.
    logger.info(
        "Obtained new installation access token for installation_id=%d (expires_at=%s)",
        installation_id,
        expires_at_str,
    )
    return new_token


# ---------------------------------------------------------------------------
# Test helpers — allow tests to reset cached state between runs.
# ---------------------------------------------------------------------------
def _reset_caches() -> None:
    """Clear all in-process caches.  Intended for tests only."""
    global _cached_jwt, _cached_jwt_exp
    with _jwt_cache_lock:
        _cached_jwt = None
        _cached_jwt_exp = 0.0
    with _install_token_cache_lock:
        _install_token_cache.clear()
