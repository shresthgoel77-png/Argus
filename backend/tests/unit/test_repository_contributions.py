import asyncio
from datetime import date
from unittest.mock import AsyncMock

import httpx
import pytest

from app.integrations.github.exceptions import GitHubAPIError, GitHubAuthError
from app.services import repository_contribution_service as service

START, END = date(2026, 10, 1), date(2026, 10, 3)
HEAD = "f" * 40


def response(data=None, status=200):
    return httpx.Response(status, json=data, request=httpx.Request("GET", "https://api.github.com/graphql"))


def commit(index=1, **changes):
    return {"oid": f"{index:040x}", "message": f"Commit {index}", "committedDate": "2026-10-02T09:00:00Z",
            "authoredDate": "2026-09-30T00:00:00Z", "url": f"https://github.com/acme/repo/commit/{index:040x}",
            "additions": 4, "deletions": 2,
            "author": {"name": "Person", "email": "private@example.test", "user": {"databaseId": 42, "login": "person"}}, **changes}


def page(nodes=None, next_page=False, cursor="cursor-1", **repo_changes):
    return response({"data": {"repository": {"databaseId": 17, "isEmpty": False,
        "object": {"oid": HEAD, "history": {"nodes": nodes or [],
                   "pageInfo": {"hasNextPage": next_page, "endCursor": cursor}}}, **repo_changes}}})


async def read(*upstream):
    client = service.RepositoryContributionClient(12)
    client._request = AsyncMock(side_effect=[response({"id": 17, "default_branch": "main"}), *upstream])
    result = await client.read_contributions("local-repo", "acme/repo", 17, START, END)
    return result, client._request


@pytest.mark.asyncio
async def test_aggregation_pins_pages_deduplicates_and_sorts_one_compatible_scope():
    first = commit(1)
    second = commit(2, committedDate="2026-10-03T03:00:00Z")
    result, request = await read(page([first], True), page([first, second]))
    assert result["status"] == "available" and result["history_complete"]
    assert result["metrics"] == {"commit_count": 2, "additions": 8, "deletions": 4,
                                 "distinct_authors": 1, "known_authors": 1, "unknown_author_commits": 0}
    assert [event["sha"] for event in result["events"]] == [second["oid"], first["oid"]]
    assert [bucket["commits"] for bucket in result["frequency"]] == [0, 1, 1]
    assert all(event["branch"] == "main" and event["pull_request"] is None for event in result["events"])
    assert "email" not in str(result) and "private@example.test" not in str(result)
    assert request.await_count == 3  # Metadata + two batched history pages; no per-commit reads.
    assert request.call_args_list[1].kwargs["json"]["variables"]["expression"] == "refs/heads/main"
    assert request.call_args_list[2].kwargs["json"]["variables"]["expression"] == HEAD
    assert request.call_args_list[2].kwargs["json"]["variables"]["after"] == "cursor-1"


@pytest.mark.asyncio
async def test_history_cap_is_partial_and_does_not_claim_window_totals():
    result, request = await read(*(page([commit(index + 1)], True, f"page-{index}") for index in range(5)))
    assert result["status"] == "partial" and not result["history_complete"]
    assert result["reason"] == "scan_limit" and result["metrics"]["commit_count"] == 5
    assert sum(bucket["commits"] for bucket in result["frequency"]) == 5
    assert request.await_count == 6


@pytest.mark.asyncio
@pytest.mark.parametrize("status,expected", [(202, "pending"), (204, "unsupported")])
async def test_pending_and_no_content_are_not_zero_and_are_never_polled(status, expected):
    result, request = await read(response(status=status))
    assert result["status"] == expected and result["metrics"] is None and result["frequency"] == []
    assert not result["history_complete"] and request.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("empty", [False, True])
async def test_confirmed_zero_and_confirmed_empty_repo(empty):
    result, _ = await read(page(isEmpty=empty, object=None) if empty else page())
    assert result["status"] == "available" and result["metrics"]["commit_count"] == 0
    assert result["metrics"]["additions"] == result["metrics"]["deletions"] == 0
    assert len(result["frequency"]) == 3


@pytest.mark.asyncio
async def test_unknown_lines_and_authors_are_partial_not_zero():
    result, _ = await read(page([commit(author=None, additions=None)]))
    assert result["status"] == "partial" and result["history_complete"]
    assert result["metrics"]["additions"] is None and result["metrics"]["distinct_authors"] is None
    assert result["metrics"]["unknown_author_commits"] == 1


@pytest.mark.asyncio
async def test_unlinked_primary_authors_use_exact_email_identity_without_exposing_email():
    result, _ = await read(page([commit(1, author={"name": "A", "email": "A@example.test", "user": None}),
                                commit(2, author={"name": "Renamed", "email": "a@example.test", "user": None})]))
    assert result["metrics"]["distinct_authors"] == 1
    assert "example.test" not in str(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [GitHubAuthError(response_status=403), GitHubAPIError(response_status=429),
    GitHubAPIError(response_status=500), GitHubAPIError(), response({"errors": [{"type": "RATE_LIMITED"}]}),
    response({"errors": [{"type": "FORBIDDEN"}], "data": {"repository": None}}), page(databaseId=999),
    page(object=None), page([commit(committedDate="2026-09-30T00:00:00Z")]), page([commit(oid="invalid")])])
async def test_upstream_failures_do_not_become_zero(failure):
    result, request = await read(failure)
    assert result["status"] == "unavailable" and result["metrics"] is None
    assert result["events"] == [] and request.await_count == 2


@pytest.mark.asyncio
async def test_mid_scan_failure_preserves_only_fully_validated_pages():
    result, _ = await read(page([commit()], True), GitHubAPIError(response_status=500))
    assert result["status"] == "partial" and result["metrics"]["commit_count"] == 1
    assert result["reason"] == "github_api_error" and not result["history_complete"]


@pytest.mark.asyncio
async def test_conflicting_duplicates_and_repeated_cursors_stop_scan():
    result, request = await read(page([commit()], True), page([commit(additions=50)]))
    assert result["status"] == "partial" and result["metrics"]["additions"] == 4
    assert result["reason"] == "invalid_provider_response"
    result, request = await read(page([commit()], True), page([commit(2)], True))
    assert result["status"] == "partial" and request.await_count == 3


@pytest.mark.asyncio
async def test_identity_mismatch_prevents_history_read():
    client = service.RepositoryContributionClient(12)
    client._request = AsyncMock(return_value=response({"id": 999, "default_branch": "main"}))
    result = await client.read_contributions("local", "acme/repo", 17, START, END)
    assert result["status"] == "unavailable" and client._request.await_count == 1


@pytest.mark.asyncio
async def test_rate_limit_headers_are_respected_without_retry():
    async with service.RepositoryContributionClient(12) as client:
        await client._observe_response(httpx.Response(403, headers={"retry-after": "120"}))
        client._request = AsyncMock(side_effect=GitHubAuthError(response_status=403))
        result = await client.read_contributions("local", "acme/repo", 17, START, END)
        assert result["reason"] == "rate_limited" and result["retry_after_seconds"] == 120
        assert client._request.await_count == 1


@pytest.mark.asyncio
async def test_exhausted_graphql_budget_stops_even_after_successful_partial_page():
    async with service.RepositoryContributionClient(12) as client:
        async def request(method, path, **kwargs):
            if method == "GET":
                return response({"id": 17, "default_branch": "main"})
            await client._observe_response(httpx.Response(200, headers={"x-ratelimit-remaining": "0", "retry-after": "180"}))
            return page([commit()], True)
        client._request = AsyncMock(side_effect=request)
        result = await client.read_contributions("local", "acme/repo", 17, START, END)
        assert result["status"] == "partial" and result["reason"] == "rate_limited"
        assert result["metrics"]["commit_count"] == 1 and result["retry_after_seconds"] == 180
        assert client._request.await_count == 2


@pytest.mark.asyncio
async def test_all_five_hundred_commits_are_aggregated_without_detail_requests():
    pages = [page([commit(offset + index + 1) for index in range(100)], offset < 400, f"page-{offset}")
             for offset in range(0, 500, 100)]
    result, request = await read(*pages)
    assert result["status"] == "available" and result["history_complete"]
    assert result["metrics"]["commit_count"] == 500 and result["metrics"]["additions"] == 2000
    assert request.await_count == 6


def arguments(**changes):
    return dict(user_id="user", repository_id="local", connection_id="connection", installation_id=12,
                github_id=17, full_name="acme/repo", start=START, end=END, **changes)


@pytest.mark.asyncio
async def test_cached_pagination_is_scoped_copied_stable_and_explicitly_expires(monkeypatch):
    result, _ = await read(page([commit(1), commit(2), commit(3)]))
    loader = AsyncMock(return_value=result)
    monkeypatch.setattr(service.RepositoryContributionClient, "read_contributions", loader)
    first = await service.get_repository_contributions(**arguments(limit=2))
    assert len(first["items"]) == 2 and first["metrics"]["commit_count"] == 3
    second = await service.get_repository_contributions(**arguments(cursor=first["next_cursor"], limit=2))
    assert second["next_cursor"] is None and len(second["items"]) == 1
    assert second["snapshot_id"] == first["snapshot_id"] and second["metrics"] == first["metrics"]
    assert not {item["sha"] for item in first["items"]} & {item["sha"] for item in second["items"]}
    first["metrics"]["commit_count"] = 999
    assert (await service.get_repository_contributions(**arguments()))["metrics"]["commit_count"] == 3
    assert loader.await_count == 1
    for field, value in [("user_id", "other"), ("connection_id", "new"), ("installation_id", 13),
                         ("repository_id", "different"), ("start", date(2026, 10, 2))]:
        args = arguments(cursor=first["next_cursor"])
        args[field] = value
        with pytest.raises(service.ContributionCursorError):
            await service.get_repository_contributions(**args)
    for cursor in ["garbage", f"{first['snapshot_id']}:0", f"{first['snapshot_id']}:-1", f"{first['snapshot_id']}:999"]:
        with pytest.raises(service.ContributionCursorError):
            await service.get_repository_contributions(**arguments(cursor=cursor))
    cache = service._caches[asyncio.get_running_loop()]
    for key, (_, data) in cache["values"].items():
        cache["values"][key] = (0, data)
    with pytest.raises(service.ContributionCursorError):
        await service.get_repository_contributions(**arguments(cursor=first["next_cursor"]))
    await service.get_repository_contributions(**arguments())
    assert loader.await_count == 2


@pytest.mark.asyncio
async def test_inflight_deduplication_cancellation_isolation_and_concurrency(monkeypatch):
    result, _ = await read(page())
    active = maximum = calls = 0
    release = asyncio.Event()
    async def load(*args):
        nonlocal active, maximum, calls
        active += 1
        calls += 1
        maximum = max(maximum, active)
        await release.wait()
        active -= 1
        return result
    monkeypatch.setattr(service.RepositoryContributionClient, "read_contributions", load)
    tasks = [asyncio.create_task(service.get_repository_contributions(**arguments())) for _ in range(2)]
    tasks += [asyncio.create_task(service.get_repository_contributions(**{**arguments(), "user_id": f"user-{index}"})) for index in range(7)]
    for _ in range(30):
        await asyncio.sleep(0)
    tasks[0].cancel()
    with pytest.raises(asyncio.CancelledError):
        await tasks[0]
    release.set()
    await asyncio.gather(*tasks[1:])
    assert maximum == 4 and calls == 8


def test_range_default_and_bounds():
    today = date(2026, 10, 19)
    start, end = service.contribution_range(None, None, today)
    assert (end - start).days == 89 and end == today
    assert service.contribution_range(START, START, today) == (START, START)
    for start, end in [(END, START), (date(2026, 1, 1), END), (START, date(2027, 1, 1)),
                       (date(1969, 1, 1), date(1969, 1, 2))]:
        with pytest.raises(ValueError):
            service.contribution_range(start, end, today)
