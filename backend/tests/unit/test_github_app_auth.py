"""Unit tests for GitHub App JWT generation and installation token caching.

All httpx calls are mocked — no real network access required.
"""

from __future__ import annotations

import time
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from app.integrations.github import app_auth
from app.integrations.github.app_auth import (
    generate_app_jwt,
    get_installation_access_token,
    _reset_caches,
    _JWT_EXPIRY_SECONDS,
    _JWT_IAT_DRIFT_SECONDS,
    _JWT_REFRESH_MARGIN_SECONDS,
    _INSTALL_TOKEN_REFRESH_MARGIN_SECONDS,
)
from app.integrations.github.exceptions import GitHubAPIError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_caches():
    """Reset module-level caches between every test."""
    _reset_caches()
    yield
    _reset_caches()


@pytest.fixture(scope="module")
def rsa_keypair():
    """Generate a test RSA keypair (2048-bit) once per module."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_key = private_key.public_key()
    return private_pem, public_key


@pytest.fixture()
def patch_settings(rsa_keypair, monkeypatch):
    """Patch settings to use the test RSA private key."""
    private_pem, _ = rsa_keypair
    mock_secret = MagicMock()
    mock_secret.get_secret_value.return_value = private_pem

    monkeypatch.setattr("app.integrations.github.app_auth.settings.github_app_id", "123456")
    monkeypatch.setattr("app.integrations.github.app_auth.settings.github_app_private_key", mock_secret)


# ---------------------------------------------------------------------------
# Tests — generate_app_jwt()
# ---------------------------------------------------------------------------

class TestGenerateAppJWT:
    """Tests for JWT creation and caching."""

    def test_jwt_is_well_formed_and_verifiable(self, patch_settings, rsa_keypair):
        """The signed JWT can be decoded with the corresponding public key."""
        _, public_key = rsa_keypair
        token = generate_app_jwt()

        decoded = pyjwt.decode(token, public_key, algorithms=["RS256"])
        assert decoded["iss"] == "123456"
        assert "iat" in decoded
        assert "exp" in decoded

    def test_jwt_iat_is_backdated(self, patch_settings, rsa_keypair):
        """iat should be ~60s before now for clock-drift tolerance."""
        _, public_key = rsa_keypair
        now = time.time()
        token = generate_app_jwt()

        decoded = pyjwt.decode(token, public_key, algorithms=["RS256"])
        # iat should be within a few seconds of (now - 60)
        expected_iat = int(now) - _JWT_IAT_DRIFT_SECONDS
        assert abs(decoded["iat"] - expected_iat) <= 2

    def test_jwt_exp_within_10_minutes(self, patch_settings, rsa_keypair):
        """exp must be at most 10 minutes (600s) ahead of now."""
        _, public_key = rsa_keypair
        now = time.time()
        token = generate_app_jwt()

        decoded = pyjwt.decode(token, public_key, algorithms=["RS256"])
        assert decoded["exp"] <= now + 600 + 2  # small tolerance

    def test_jwt_uses_rs256_algorithm(self, patch_settings, rsa_keypair):
        """The JWT header must specify RS256."""
        token = generate_app_jwt()
        header = pyjwt.get_unverified_header(token)
        assert header["alg"] == "RS256"

    def test_jwt_caching_returns_same_token(self, patch_settings):
        """Calling generate_app_jwt() twice should return the cached value."""
        token1 = generate_app_jwt()
        token2 = generate_app_jwt()
        assert token1 == token2

    def test_jwt_refreshes_when_near_expiry(self, patch_settings):
        """After advancing time to near expiry, a new JWT should be generated."""
        real_time = time.time()

        with patch("app.integrations.github.app_auth.time.time", return_value=real_time):
            token1 = generate_app_jwt()

        # Advance the clock so the cached JWT appears about to expire AND
        # the new JWT will have different iat/exp values (producing a
        # different signature).
        future_time = real_time + _JWT_EXPIRY_SECONDS - _JWT_REFRESH_MARGIN_SECONDS + 10
        with patch("app.integrations.github.app_auth.time.time", return_value=future_time):
            token2 = generate_app_jwt()

        assert token1 != token2


# ---------------------------------------------------------------------------
# Tests — get_installation_access_token()
# ---------------------------------------------------------------------------

def _make_token_response(token: str = "ghs_test_token_123", hours_from_now: float = 1.0):
    """Build a mock httpx.Response for the installation token endpoint."""
    expires_at = datetime.now(tz=timezone.utc) + timedelta(hours=hours_from_now)
    body = {
        "token": token,
        "expires_at": expires_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    response = MagicMock()
    response.status_code = 201
    response.json.return_value = body
    return response


class TestGetInstallationAccessToken:
    """Tests for installation token fetching and caching."""

    @pytest.mark.asyncio
    async def test_fetches_token_from_github(self, patch_settings):
        """First call should POST to GitHub and return the token."""
        mock_response = _make_token_response("ghs_fresh_token")

        with patch("app.integrations.github.app_auth.httpx.AsyncClient") as MockClient:
            mock_http = AsyncMock()
            mock_http.post.return_value = mock_response
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_http

            token = await get_installation_access_token(installation_id=42)

        assert token == "ghs_fresh_token"
        mock_http.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_caches_token_before_expiry(self, patch_settings):
        """Second call should return the cached token without another POST."""
        mock_response = _make_token_response("ghs_cached_token")

        with patch("app.integrations.github.app_auth.httpx.AsyncClient") as MockClient:
            mock_http = AsyncMock()
            mock_http.post.return_value = mock_response
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_http

            token1 = await get_installation_access_token(installation_id=42)
            token2 = await get_installation_access_token(installation_id=42)

        assert token1 == token2 == "ghs_cached_token"
        # Only one POST should have been made.
        assert mock_http.post.call_count == 1

    @pytest.mark.asyncio
    async def test_refreshes_token_when_near_expiry(self, patch_settings):
        """When the cached token is near expiry, a fresh one should be fetched."""
        mock_response_1 = _make_token_response("ghs_old_token")
        mock_response_2 = _make_token_response("ghs_new_token")

        with patch("app.integrations.github.app_auth.httpx.AsyncClient") as MockClient:
            mock_http = AsyncMock()
            mock_http.post.side_effect = [mock_response_1, mock_response_2]
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_http

            token1 = await get_installation_access_token(installation_id=42)
            assert token1 == "ghs_old_token"

            # Simulate approaching expiry by modifying the cached expires_at.
            with app_auth._install_token_cache_lock:
                _, expires_at = app_auth._install_token_cache[42]
                app_auth._install_token_cache[42] = (
                    "ghs_old_token",
                    time.time() + _INSTALL_TOKEN_REFRESH_MARGIN_SECONDS - 1,
                )

            token2 = await get_installation_access_token(installation_id=42)
            assert token2 == "ghs_new_token"
            assert mock_http.post.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_on_github_error_response(self, patch_settings):
        """A non-2xx response should raise GitHubAPIError."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"message": "Bad credentials"}
        mock_response.text = '{"message": "Bad credentials"}'

        with patch("app.integrations.github.app_auth.httpx.AsyncClient") as MockClient:
            mock_http = AsyncMock()
            mock_http.post.return_value = mock_response
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_http

            with pytest.raises(GitHubAPIError):
                await get_installation_access_token(installation_id=42)
