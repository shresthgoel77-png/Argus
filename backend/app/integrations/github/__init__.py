"""GitHub App integration module.

Provides JWT-based authentication, installation access token management,
and a minimal async REST client for GitHub API calls.
"""

from app.integrations.github.exceptions import (
    GitHubAPIError,
    GitHubAuthError,
    GitHubNotFoundError,
    GitHubRateLimitError,
)
from app.integrations.github.app_auth import (
    generate_app_jwt,
    get_installation_access_token,
)
from app.integrations.github.client import GitHubAppClient

__all__ = [
    "GitHubAPIError",
    "GitHubAuthError",
    "GitHubNotFoundError",
    "GitHubRateLimitError",
    "generate_app_jwt",
    "get_installation_access_token",
    "GitHubAppClient",
]
