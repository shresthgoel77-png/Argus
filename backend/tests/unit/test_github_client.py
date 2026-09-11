"""Unit tests for GitHubAppClient — async REST wrapper.

All httpx calls are mocked — no real network access required.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.integrations.github.client import GitHubAppClient
from app.integrations.github.exceptions import (
    GitHubAPIError,
    GitHubAuthError,
    GitHubNotFoundError,
    GitHubRateLimitError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(
    status_code: int = 200,
    json_data: dict | list | None = None,
    headers: dict | None = None,
    text: str = "",
) -> MagicMock:
    """Create a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.headers = headers or {}
    resp.text = text or json.dumps(json_data or {})
    return resp


def _repo(id: int, name: str, private: bool = False, branch: str = "main") -> dict:
    """Convenience builder for a GitHub-style repository dict."""
    return {
        "id": id,
        "full_name": name,
        "private": private,
        "default_branch": branch,
        "node_id": "unused",
        "owner": {"login": "test"},
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def _patch_auth():
    """Patch auth functions so client doesn't try to sign real JWTs."""
    with patch(
        "app.integrations.github.client.get_installation_access_token",
        new_callable=AsyncMock,
        return_value="ghs_mocked_token",
    ), patch(
        "app.integrations.github.client.generate_app_jwt",
        return_value="eyJ_mocked_app_jwt",
    ):
        yield


# ---------------------------------------------------------------------------
# Tests — get_installation()
# ---------------------------------------------------------------------------

class TestGetInstallation:
    @pytest.mark.asyncio
    async def test_returns_installation_dict(self, _patch_auth):
        installation_data = {"id": 99, "app_id": 123, "target_type": "Organization"}
        mock_resp = _mock_response(200, json_data=installation_data)

        async with GitHubAppClient(installation_id=1) as client:
            with patch.object(client._http, "request", new_callable=AsyncMock, return_value=mock_resp):
                result = await client.get_installation(99)

        assert result == installation_data

    @pytest.mark.asyncio
    async def test_uses_app_jwt_auth(self, _patch_auth):
        """get_installation() should authenticate with the App JWT, not an installation token."""
        mock_resp = _mock_response(200, json_data={"id": 99})

        async with GitHubAppClient(installation_id=1) as client:
            with patch.object(client._http, "request", new_callable=AsyncMock, return_value=mock_resp) as mock_request:
                await client.get_installation(99)

        # The Authorization header should contain the mocked app JWT.
        call_kwargs = mock_request.call_args
        auth_header = call_kwargs.kwargs.get("headers", {}) if call_kwargs.kwargs else call_kwargs[1].get("headers", {})
        assert "eyJ_mocked_app_jwt" in auth_header.get("Authorization", "")


# ---------------------------------------------------------------------------
# Tests — list_installation_repositories() + pagination
# ---------------------------------------------------------------------------

class TestListInstallationRepositories:
    @pytest.mark.asyncio
    async def test_single_page(self, _patch_auth):
        """Returns correctly normalized repos from a single page."""
        repos = [_repo(1, "org/repo-a", True, "develop"), _repo(2, "org/repo-b")]
        mock_resp = _mock_response(200, json_data={"repositories": repos}, headers={})

        async with GitHubAppClient(installation_id=1) as client:
            with patch.object(client._http, "request", new_callable=AsyncMock, return_value=mock_resp):
                result = await client.list_installation_repositories()

        assert len(result) == 2
        assert result[0] == {"id": 1, "full_name": "org/repo-a", "private": True, "default_branch": "develop"}
        assert result[1] == {"id": 2, "full_name": "org/repo-b", "private": False, "default_branch": "main"}

    @pytest.mark.asyncio
    async def test_multi_page_pagination(self, _patch_auth):
        """Correctly follows pagination across multiple pages."""
        page1_repos = [_repo(i, f"org/repo-{i}") for i in range(1, 4)]
        page2_repos = [_repo(i, f"org/repo-{i}") for i in range(4, 6)]

        page1_resp = _mock_response(
            200,
            json_data={"total_count": 5, "repositories": page1_repos},
            headers={"link": '<https://api.github.com/installation/repositories?page=2>; rel="next"'},
        )
        page2_resp = _mock_response(
            200,
            json_data={"total_count": 5, "repositories": page2_repos},
            headers={},  # No next link — last page
        )

        async with GitHubAppClient(installation_id=1) as client:
            with patch.object(
                client._http, "request", new_callable=AsyncMock, side_effect=[page1_resp, page2_resp]
            ):
                result = await client.list_installation_repositories()

        assert len(result) == 5
        assert [r["id"] for r in result] == [1, 2, 3, 4, 5]

    @pytest.mark.asyncio
    async def test_empty_repositories(self, _patch_auth):
        """Handles zero repositories gracefully."""
        mock_resp = _mock_response(200, json_data={"repositories": []}, headers={})

        async with GitHubAppClient(installation_id=1) as client:
            with patch.object(client._http, "request", new_callable=AsyncMock, return_value=mock_resp):
                result = await client.list_installation_repositories()

        assert result == []


# ---------------------------------------------------------------------------
# Tests — error mapping
# ---------------------------------------------------------------------------

class TestErrorMapping:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status_code, expected_exc",
        [
            (401, GitHubAuthError),
            (403, GitHubAuthError),
            (404, GitHubNotFoundError),
            (429, GitHubRateLimitError),
            (500, GitHubAPIError),
        ],
    )
    async def test_status_code_maps_to_correct_exception(
        self, _patch_auth, status_code, expected_exc
    ):
        mock_resp = _mock_response(
            status_code,
            json_data={"message": "Something went wrong"},
        )

        async with GitHubAppClient(installation_id=1) as client:
            with patch.object(client._http, "request", new_callable=AsyncMock, return_value=mock_resp):
                with pytest.raises(expected_exc):
                    await client.get_installation(99)
