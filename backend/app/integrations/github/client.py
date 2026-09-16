"""Thin async REST client for GitHub API calls.

Uses installation access tokens (not the raw App JWT) for all repository /
installation-scoped calls.  The App JWT is only used internally to *obtain*
those installation tokens.

This module has **no dependency on FastAPI request context** — it is a plain
injectable client that can be used from background tasks, CLI tooling, etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.logging import get_logger
from app.integrations.github.app_auth import (
    generate_app_jwt,
    get_installation_access_token,
)
from app.integrations.github.exceptions import (
    GitHubAPIError,
    GitHubNotFoundError,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_GITHUB_API_BASE = "https://api.github.com"
_DEFAULT_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
_MAX_PER_PAGE = 100  # GitHub's max per_page value


def _redact_auth_headers(headers: dict[str, str]) -> dict[str, str]:
    """Return a copy of *headers* with Authorization values replaced."""
    redacted = dict(headers)
    if "Authorization" in redacted:
        redacted["Authorization"] = "Bearer [REDACTED]"
    return redacted


def _raise_for_status(response: httpx.Response) -> None:
    """Raise the appropriate GitHubAPIError subclass for non-2xx responses."""
    if 200 <= response.status_code < 300:
        return
    raise GitHubAPIError.from_response(response)


@dataclass
class PostedComment:
    """Represents a GitHub comment created via the API."""
    id: int


class GitHubAppClient:
    """Async REST client scoped to a single GitHub App installation.

    Usage::

        async with GitHubAppClient(installation_id=12345) as client:
            repos = await client.list_installation_repositories()

    All requests are authenticated with a short-lived installation access
    token, automatically obtained (and cached) via
    :func:`get_installation_access_token`.
    """

    def __init__(self, installation_id: int) -> None:
        self._installation_id = installation_id
        self._http: httpx.AsyncClient | None = None

    # -- Context manager ----------------------------------------------------

    async def __aenter__(self) -> "GitHubAppClient":
        self._http = httpx.AsyncClient(
            base_url=_GITHUB_API_BASE,
            headers=_DEFAULT_HEADERS,
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    # -- Internal helpers ---------------------------------------------------

    async def _auth_headers(self, *, use_app_jwt: bool = False) -> dict[str, str]:
        """Build Authorization header using installation token or app JWT.

        Args:
            use_app_jwt: If True use the raw App JWT (only for endpoints that
                require app-level auth, e.g. ``GET /app/installations/{id}``).
        """
        if use_app_jwt:
            token = generate_app_jwt()
        else:
            token = await get_installation_access_token(self._installation_id)
        return {"Authorization": f"Bearer {token}"}

    async def _request(
        self,
        method: str,
        url: str,
        *,
        use_app_jwt: bool = False,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Send a single authenticated request.

        Raises:
            GitHubAPIError: On any non-2xx response.
        """
        if self._http is None:
            raise RuntimeError(
                "GitHubAppClient must be used as an async context manager "
                "(async with GitHubAppClient(...) as client:)"
            )

        auth_headers = await self._auth_headers(use_app_jwt=use_app_jwt)

        # SECURITY: Log the request but redact the Authorization header.
        logger.debug(
            "GitHub API %s %s headers=%s params=%s",
            method,
            url,
            _redact_auth_headers({**_DEFAULT_HEADERS, **auth_headers}),
            params,
        )

        kwargs = {"headers": auth_headers, "params": params}
        if json is not None:
            kwargs["json"] = json
            
        response = await self._http.request(
            method, url, **kwargs
        )

        logger.debug(
            "GitHub API response: %s %s -> %d",
            method,
            url,
            response.status_code,
        )

        _raise_for_status(response)
        return response

    # -- Public API ---------------------------------------------------------

    async def post_issue_comment(self, owner: str, repo: str, issue_number: int, body: str) -> PostedComment:
        """Post a comment to an issue or pull request.

        Defensively truncates the body to GitHub's max limit before sending.
        Uses the installation access token.
        """
        # GitHub limits issue comment bodies to 65536 characters.
        safe_body = body[:65536]
        
        response = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            json={"body": safe_body},
        )
        data = response.json()
        return PostedComment(id=data["id"])

    async def get_installation(self, installation_id: int) -> dict[str, Any]:
        """Fetch metadata for a GitHub App installation.

        Uses the *App JWT* (not an installation token) because the endpoint
        ``GET /app/installations/{id}`` requires app-level auth.

        Args:
            installation_id: Numeric installation ID.

        Returns:
            The installation metadata dict as returned by GitHub.
        """
        response = await self._request(
            "GET",
            f"/app/installations/{installation_id}",
            use_app_jwt=True,
        )
        return response.json()

    async def list_installation_repositories(self) -> list[dict[str, Any]]:
        """List all repositories accessible to this installation.

        Handles GitHub pagination (``Link`` header / ``page`` parameter) and
        returns normalized dicts containing at least:

        - ``id``
        - ``full_name``
        - ``private``
        - ``default_branch``

        Returns:
            A list of normalized repository dicts.
        """
        all_repos: list[dict[str, Any]] = []
        page = 1

        while True:
            response = await self._request(
                "GET",
                "/installation/repositories",
                params={"per_page": _MAX_PER_PAGE, "page": page},
            )
            data = response.json()
            repositories = data.get("repositories", [])

            for repo in repositories:
                all_repos.append(
                    {
                        "id": repo["id"],
                        "full_name": repo["full_name"],
                        "private": repo["private"],
                        "default_branch": repo.get("default_branch", "main"),
                    }
                )

            # Check if there is a next page via Link header.
            link_header = response.headers.get("link", "")
            if 'rel="next"' not in link_header:
                break
            page += 1

        logger.info(
            "Listed %d repositories for installation_id=%d",
            len(all_repos),
            self._installation_id,
        )
        return all_repos

    async def get_repository_content(
        self, full_name: str, path: str
    ) -> dict[str, Any] | list[dict[str, Any]] | None:
        """Fetch file or directory content from a repository."""
        try:
            response = await self._request(
                "GET",
                f"/repos/{full_name}/contents/{path}"
            )
            return response.json()
        except GitHubNotFoundError:
            return None

    async def get_pull_request(self, full_name: str, number: int) -> dict[str, Any] | None:
        """Fetch one pull request resource without following related links."""
        try:
            response = await self._request("GET", f"/repos/{full_name}/pulls/{number}")
            data = response.json()
            return data if isinstance(data, dict) else None
        except GitHubNotFoundError:
            return None

    async def get_issue(self, full_name: str, number: int) -> dict[str, Any] | None:
        """Fetch one issue resource without following related links."""
        try:
            response = await self._request("GET", f"/repos/{full_name}/issues/{number}")
            data = response.json()
            return data if isinstance(data, dict) else None
        except GitHubNotFoundError:
            return None

    async def get_collaborator_permission(
        self, full_name: str, username: str
    ) -> str:
        """Return a collaborator's effective permission on a repository."""
        response = await self._request(
            "GET",
            f"/repos/{full_name}/collaborators/{username}/permission",
        )
        permission = response.json().get("permission")
        if not isinstance(permission, str):
            raise GitHubAPIError("GitHub returned no collaborator permission")
        return permission

    async def list_dependabot_alerts(self, full_name: str) -> list[dict[str, Any]]:
        """List dependabot alerts for a repository with pagination."""
        all_alerts: list[dict[str, Any]] = []
        page = 1
        while True:
            try:
                response = await self._request(
                    "GET",
                    f"/repos/{full_name}/dependabot/alerts",
                    params={"per_page": _MAX_PER_PAGE, "page": page},
                )
                data = response.json()
                if not isinstance(data, list):
                    # In case the API returns an object instead of a list incorrectly, though it shouldn't
                    break
                all_alerts.extend(data)
                
                link_header = response.headers.get("link", "")
                if 'rel="next"' not in link_header:
                    break
                page += 1
            except GitHubNotFoundError:
                # 404 indicates dependable is disabled or repo not found
                return []
        
        return all_alerts

    async def get_branch_protection(
        self, full_name: str, branch: str
    ) -> dict[str, Any] | None:
        """Fetch branch protection rules for a repository branch."""
        try:
            response = await self._request(
                "GET",
                f"/repos/{full_name}/branches/{branch}/protection"
            )
            return response.json()
        except GitHubNotFoundError:
            return None

async def get_branch_protection(
    installation_id: int, full_name: str, branch: str
) -> dict[str, Any] | None:
    """Fetch branch protection rules for a repository branch standalone."""
    from app.integrations.github.exceptions import GitHubNotFoundError
    
    async with GitHubAppClient(installation_id) as client:
        try:
            response = await client._request(
                "GET",
                f"/repos/{full_name}/branches/{branch}/protection"
            )
            return response.json()
        except GitHubNotFoundError:
            return None
