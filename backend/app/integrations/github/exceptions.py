"""GitHub API error hierarchy.

All exceptions extend the application-wide AppError base class so they
are handled uniformly by the global error handler in app.api.errors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx

from app.core.exceptions import AppError


class GitHubAPIError(AppError):
    """Base error for any non-success response from the GitHub REST API.

    Attributes:
        response_status: The original HTTP status returned by GitHub.
    """

    def __init__(
        self,
        message: str = "GitHub API request failed",
        *,
        response_status: int | None = None,
    ):
        self.response_status = response_status
        super().__init__(
            code="github_api_error",
            message=message,
            status_code=502,  # Upstream API failure
        )

    # ------------------------------------------------------------------
    # Factory: map an httpx response to the most specific subclass.
    # ------------------------------------------------------------------
    @classmethod
    def from_response(cls, response: "httpx.Response") -> "GitHubAPIError":
        """Create the appropriate GitHubAPIError subclass from an httpx response."""
        status = response.status_code
        try:
            body = response.json()
            detail = body.get("message", response.text[:200])
        except Exception:
            detail = response.text[:200] if response.text else "No response body"

        if status in (401, 403):
            return GitHubAuthError(
                message=f"GitHub authentication/authorization failed: {detail}",
                response_status=status,
            )
        if status == 404:
            return GitHubNotFoundError(
                message=f"GitHub resource not found: {detail}",
                response_status=status,
            )
        if status == 429:
            return GitHubRateLimitError(
                message=f"GitHub API rate limit exceeded: {detail}",
                response_status=status,
            )
        return cls(
            message=f"GitHub API error ({status}): {detail}",
            response_status=status,
        )


class GitHubAuthError(GitHubAPIError):
    """Raised on 401 Unauthorized or 403 Forbidden from the GitHub API."""

    def __init__(
        self,
        message: str = "GitHub authentication failed",
        *,
        response_status: int | None = None,
    ):
        # Bypass GitHubAPIError.__init__ to set a different code/status_code
        self.response_status = response_status
        AppError.__init__(
            self,
            code="github_permission_error" if response_status == 403 else "github_auth_error",
            message=message,
            status_code=403 if response_status == 403 else 502,
        )


class GitHubInstallationError(GitHubAPIError):
    """The configured App cannot authenticate the stored installation."""

    def __init__(self, installation_id: int):
        self.response_status = 404
        AppError.__init__(
            self, code="github_installation_unavailable", status_code=409,
            message=(f"GitHub installation {installation_id} is unavailable to the configured App. "
                     "In Settings, reconnect the same GitHub account and include this repository. "
                     "Existing records have been preserved; do not substitute another account's installation."),
        )


class GitHubNotFoundError(GitHubAPIError):
    """Raised on 404 Not Found from the GitHub API."""

    def __init__(
        self,
        message: str = "GitHub resource not found",
        *,
        response_status: int | None = None,
    ):
        self.response_status = response_status
        AppError.__init__(
            self,
            code="github_not_found",
            message=message,
            status_code=404,
        )


class GitHubRateLimitError(GitHubAPIError):
    """Raised on 429 Too Many Requests from the GitHub API."""

    def __init__(
        self,
        message: str = "GitHub API rate limit exceeded",
        *,
        response_status: int | None = None,
    ):
        self.response_status = response_status
        AppError.__init__(
            self,
            code="github_rate_limit",
            message=message,
            status_code=429,
        )
