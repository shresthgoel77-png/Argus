import uuid
from unittest.mock import AsyncMock

import pytest

from app.services import repository_contribution_service as service


@pytest.mark.asyncio
async def test_contribution_read_requires_authentication(async_client, monkeypatch):
    read = AsyncMock()
    monkeypatch.setattr(service, "get_repository_contributions", read)
    assert (await async_client.get(f"/api/v1/repositories/{uuid.uuid4()}/contributions")).status_code == 401
    read.assert_not_called()


@pytest.mark.asyncio
async def test_current_repo_and_connection_ownership_checked_before_cache(authorized_client, test_user_repository, test_user, db_session, monkeypatch):
    from app.models.user import User
    from app.models.github_connection import GitHubConnection

    read = AsyncMock(return_value={"status": "pending"})
    monkeypatch.setattr(service, "get_repository_contributions", read)
    path = f"/api/v1/repositories/{test_user_repository.id}/contributions"
    response = await authorized_client.get(path)
    assert response.status_code == 200 and response.headers["cache-control"] == "private, no-store"
    args = read.call_args.kwargs
    assert args["user_id"] == str(test_user.id) and args["repository_id"] == str(test_user_repository.id)
    assert args["installation_id"] == test_user_repository.connection.installation_id
    assert args["connection_id"] == str(test_user_repository.connection_id)
    assert args["github_id"] == test_user_repository.github_repo_id
    assert (args["end"] - args["start"]).days == 89
    other = User(email=f"other-{uuid.uuid4()}@example.test", auth_provider="development", external_auth_id=str(uuid.uuid4()))
    db_session.add(other)
    db_session.flush()
    db_session.query(GitHubConnection).filter_by(id=test_user_repository.connection_id).update({"user_id": other.id})
    db_session.commit()
    read.reset_mock()
    assert (await authorized_client.get(path, params={"cursor": "old:20"})).status_code == 404
    assert (await authorized_client.get(f"/api/v1/repositories/{uuid.uuid4()}/contributions")).status_code == 404
    read.assert_not_called()


@pytest.mark.asyncio
async def test_contribution_range_limit_and_cursor_contract(authorized_client, test_user_repository, monkeypatch):
    read = AsyncMock(return_value={"status": "available"})
    monkeypatch.setattr(service, "get_repository_contributions", read)
    path = f"/api/v1/repositories/{test_user_repository.id}/contributions"
    for params in [{"start": "invalid"}, {"limit": 0}, {"limit": 101}, {"start": "2026-01-01", "end": "2026-10-01"},
                   {"start": "2026-10-03", "end": "2026-10-01"}, {"end": "2099-01-01"}, {"cursor": "x" * 101}]:
        assert (await authorized_client.get(path, params=params)).status_code == 422
    read.assert_not_called()
    read.side_effect = service.ContributionCursorError("Contribution snapshot expired")
    result = await authorized_client.get(path, params={"start": "2026-10-01", "end": "2026-10-03", "limit": 10, "cursor": "old:10"})
    assert result.status_code == 409
    assert read.call_args.kwargs["cursor"] == "old:10" and read.call_args.kwargs["limit"] == 10
