import uuid
from unittest.mock import AsyncMock

import pytest

from app.services import activity_metadata_service as service


@pytest.mark.asyncio
async def test_new_metadata_read_requires_authentication(async_client, monkeypatch):
    read = AsyncMock()
    monkeypatch.setattr(service, "get_activity_metadata", read)
    response = await async_client.get(f"/api/v1/repositories/{uuid.uuid4()}/activity-metadata")
    assert response.status_code == 401
    read.assert_not_called()


@pytest.mark.asyncio
async def test_metadata_uses_current_ownership_before_any_cache_or_github(authorized_client, test_user_repository, test_user, db_session, monkeypatch):
    from app.models.user import User
    from app.models.github_connection import GitHubConnection

    read = AsyncMock(return_value=service.unavailable_metadata(str(test_user_repository.id)))
    monkeypatch.setattr(service, "get_activity_metadata", read)
    path = f"/api/v1/repositories/{test_user_repository.id}/activity-metadata"
    response = await authorized_client.get(path)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert read.call_args.kwargs == {
        "user_id": str(test_user.id), "repository_id": str(test_user_repository.id),
        "connection_id": str(test_user_repository.connection_id),
        "installation_id": test_user_repository.connection.installation_id,
        "github_id": test_user_repository.github_repo_id, "full_name": test_user_repository.full_name,
    }
    # Same URL after ownership is revoked must not reach even the cached adapter.
    other = User(email=f"other-{uuid.uuid4()}@example.test", auth_provider="development", external_auth_id=str(uuid.uuid4()))
    db_session.add(other)
    db_session.flush()
    db_session.query(GitHubConnection).filter_by(id=test_user_repository.connection_id).update({"user_id": other.id})
    db_session.commit()
    read.reset_mock()
    assert (await authorized_client.get(path)).status_code == 404
    read.assert_not_called()
    assert (await authorized_client.get(f"/api/v1/repositories/{uuid.uuid4()}/activity-metadata")).status_code == 404
    read.assert_not_called()


@pytest.mark.asyncio
async def test_connected_repository_collection_is_not_an_installation_page(authorized_client, test_user_repository, db_session):
    from app.models.repository import Repository
    db_session.add_all([Repository(connection_id=test_user_repository.connection_id, github_repo_id=900000 + index,
                                  full_name=f"test-org/repo-{index}", default_branch="main", monitoring_enabled=False)
                        for index in range(105)])
    db_session.commit()
    response = await authorized_client.get("/api/v1/repositories")
    assert response.status_code == 200
    assert len(response.json()) == 106
