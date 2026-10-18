import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from app.integrations.github.exceptions import GitHubAuthError
from app.services import activity_metadata_service as service


def response(data, headers=None):
    return httpx.Response(200, json=data, headers=headers,
                          request=httpx.Request("GET", "https://api.github.com/repos/acme/repo"))


def data(**overrides):
    return {"id": 42, "language": "TypeScript", "description": "A repository", "topics": ["tools"],
            "stargazers_count": 0, "forks_count": 2, "open_issues_count": 7,
            "updated_at": "2026-10-18T00:00:00Z", "temp_clone_token": "must-never-be-returned", **overrides}


@pytest.mark.asyncio
async def test_metadata_uses_two_single_resource_reads_and_combined_counter():
    client = service.ActivityMetadataClient(installation_id=12)
    client._request = AsyncMock(side_effect=[response(data()), response({"TypeScript": 900, "CSS": 100})])
    result = await client.read_metadata("repo-id", "acme/repo", 42)
    assert result["primary_language"] == "TypeScript"
    assert result["primary_language_status"] == "known"
    assert result["stars"] == 0 and result["forks"] == 2
    assert result["open_issues_and_pull_requests"] == 7
    assert "open_issues_count" not in result and "temp_clone_token" not in result
    assert result["language_bytes"] == {"TypeScript": 900, "CSS": 100}
    assert client._request.call_args_list[0].args == ("GET", "/repos/acme/repo")
    assert client._request.call_args_list[1].args == ("GET", "/repos/acme/repo/languages")
    assert client._request.await_count == 2  # No issue/PR list, installation list, or pagination scan.


@pytest.mark.asyncio
@pytest.mark.parametrize("language,present,expected", [(None, True, "none"), (None, False, "unknown"), ("", True, "unknown")])
async def test_null_language_is_distinct_from_missing_or_invalid_metadata(language, present, expected):
    metadata = data(language=language)
    if not present:
        metadata.pop("language")
    client = service.ActivityMetadataClient(12)
    client._request = AsyncMock(side_effect=[response(metadata), response({})])
    result = await client.read_metadata("repo-id", "acme/repo", 42)
    assert result["primary_language_status"] == expected
    assert result["languages_status"] == "available" and result["language_bytes"] == {}


@pytest.mark.asyncio
async def test_language_failure_keeps_available_primary_metadata():
    client = service.ActivityMetadataClient(12)
    client._request = AsyncMock(side_effect=[response(data()), GitHubAuthError(response_status=403)])
    result = await client.read_metadata("repo-id", "acme/repo", 42)
    assert result["metadata_status"] == "available" and result["primary_language"] == "TypeScript"
    assert result["languages_status"] == "unavailable" and result["language_bytes"] is None
    assert result["languages_error"] == "github_permission_error"


@pytest.mark.asyncio
@pytest.mark.parametrize("headers,languages", [({}, {"Python": -1}), ({}, []),
    ({"link": '<https://api.github.com/next?page=2>; rel="next"'}, {"Python": 1})])
async def test_invalid_or_paginated_byte_data_is_not_claimed_complete(headers, languages):
    client = service.ActivityMetadataClient(12)
    client._request = AsyncMock(side_effect=[response(data()), response(languages, headers)])
    result = await client.read_metadata("repo-id", "acme/repo", 42)
    assert result["primary_language_status"] == "known"
    assert result["languages_status"] == "unavailable" and result["language_bytes"] is None


@pytest.mark.asyncio
async def test_identity_mismatch_and_permission_failure_cannot_become_empty_language_or_counts():
    for value in [response(data(id=99)), GitHubAuthError("Sensitive upstream message", response_status=403)]:
        client = service.ActivityMetadataClient(12)
        client._request = AsyncMock(side_effect=[value])
        result = await client.read_metadata("repo-id", "acme/repo", 42)
        assert result["primary_language_status"] == "unknown"
        assert result["metadata_status"] == "unavailable"
        assert result["open_issues_and_pull_requests"] is None and result["stars"] is None
        assert "Sensitive" not in str(result)
        assert client._request.await_count == 1


def scope(**overrides):
    return {"user_id": "user-a", "repository_id": "repo-a", "connection_id": "connection-a",
            "installation_id": 12, "github_id": 42, "full_name": "acme/repo", **overrides}


@pytest.mark.asyncio
async def test_cache_single_flight_scope_and_expiry(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(service.time, "monotonic", lambda: clock[0])
    calls = []

    class Client:
        def __init__(self, **kwargs): calls.append(kwargs)
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def read_metadata(self, repo_id, *args):
            await asyncio.sleep(0)
            return {**service.unavailable_metadata(repo_id), "metadata_status": "available",
                    "primary_language_status": "none", "languages_status": "available", "language_bytes": {}}

    monkeypatch.setattr(service, "ActivityMetadataClient", Client)
    one, two = await asyncio.gather(service.get_activity_metadata(**scope()), service.get_activity_metadata(**scope()))
    assert len(calls) == 1 and one == two
    one["language_bytes"]["mutated"] = 1
    assert (await service.get_activity_metadata(**scope()))["language_bytes"] == {}
    await service.get_activity_metadata(**scope(user_id="user-b"))
    await service.get_activity_metadata(**scope(connection_id="connection-b", installation_id=13))
    assert len(calls) == 3
    clock[0] += 61
    await service.get_activity_metadata(**scope())
    assert len(calls) == 4


@pytest.mark.asyncio
async def test_concurrency_is_bounded_and_cancelling_one_waiter_does_not_cancel_shared_read(monkeypatch):
    active = 0
    maximum = 0
    gate = asyncio.Event()

    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def read_metadata(self, repo_id, *args):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            await gate.wait()
            active -= 1
            return service.unavailable_metadata(repo_id)

    monkeypatch.setattr(service, "ActivityMetadataClient", Client)
    first = asyncio.create_task(service.get_activity_metadata(**scope()))
    shared = asyncio.create_task(service.get_activity_metadata(**scope()))
    tasks = [asyncio.create_task(service.get_activity_metadata(**scope(repository_id=f"repo-{i}"))) for i in range(8)]
    for _ in range(10): await asyncio.sleep(0)
    assert maximum == 4
    first.cancel()
    with pytest.raises(asyncio.CancelledError): await first
    gate.set()
    assert (await shared)["repository_id"] == "repo-a"
    await asyncio.gather(*tasks)
    assert maximum == 4
