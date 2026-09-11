"""Unit tests for the GitHub exceptions hierarchy.

Validates from_response() mapping and AppError inheritance.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core.exceptions import AppError
from app.integrations.github.exceptions import (
    GitHubAPIError,
    GitHubAuthError,
    GitHubNotFoundError,
    GitHubRateLimitError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(status_code: int, message: str = "error") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"message": message}
    resp.text = f'{{"message": "{message}"}}'
    return resp


# ---------------------------------------------------------------------------
# Inheritance
# ---------------------------------------------------------------------------

class TestInheritance:
    def test_github_api_error_is_app_error(self):
        assert issubclass(GitHubAPIError, AppError)

    def test_github_auth_error_is_github_api_error(self):
        assert issubclass(GitHubAuthError, GitHubAPIError)

    def test_github_not_found_error_is_github_api_error(self):
        assert issubclass(GitHubNotFoundError, GitHubAPIError)

    def test_github_rate_limit_error_is_github_api_error(self):
        assert issubclass(GitHubRateLimitError, GitHubAPIError)

    def test_all_are_catchable_as_app_error(self):
        for cls in (GitHubAPIError, GitHubAuthError, GitHubNotFoundError, GitHubRateLimitError):
            exc = cls()
            assert isinstance(exc, AppError)


# ---------------------------------------------------------------------------
# from_response() mapping
# ---------------------------------------------------------------------------

class TestFromResponse:
    @pytest.mark.parametrize(
        "status, expected_type, expected_code",
        [
            (401, GitHubAuthError, "github_auth_error"),
            (403, GitHubAuthError, "github_auth_error"),
            (404, GitHubNotFoundError, "github_not_found"),
            (429, GitHubRateLimitError, "github_rate_limit"),
            (500, GitHubAPIError, "github_api_error"),
            (502, GitHubAPIError, "github_api_error"),
            (422, GitHubAPIError, "github_api_error"),
        ],
    )
    def test_maps_status_to_correct_subclass(self, status, expected_type, expected_code):
        resp = _mock_response(status, "test message")
        exc = GitHubAPIError.from_response(resp)

        assert type(exc) is expected_type
        assert exc.code == expected_code
        assert exc.response_status == status
        assert "test message" in exc.message

    def test_preserves_response_status(self):
        resp = _mock_response(403, "Forbidden")
        exc = GitHubAPIError.from_response(resp)
        assert exc.response_status == 403

    def test_handles_non_json_body(self):
        resp = MagicMock()
        resp.status_code = 500
        resp.json.side_effect = ValueError("not json")
        resp.text = "Internal Server Error"
        exc = GitHubAPIError.from_response(resp)
        assert "Internal Server Error" in exc.message


# ---------------------------------------------------------------------------
# Default attributes
# ---------------------------------------------------------------------------

class TestDefaultAttributes:
    def test_github_api_error_defaults(self):
        exc = GitHubAPIError()
        assert exc.code == "github_api_error"
        assert exc.status_code == 502
        assert exc.response_status is None

    def test_github_auth_error_defaults(self):
        exc = GitHubAuthError()
        assert exc.code == "github_auth_error"
        assert exc.status_code == 401

    def test_github_not_found_defaults(self):
        exc = GitHubNotFoundError()
        assert exc.code == "github_not_found"
        assert exc.status_code == 404

    def test_github_rate_limit_defaults(self):
        exc = GitHubRateLimitError()
        assert exc.code == "github_rate_limit"
        assert exc.status_code == 429
