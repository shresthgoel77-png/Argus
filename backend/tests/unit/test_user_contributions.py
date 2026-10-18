import asyncio
from datetime import date, datetime, timezone
from types import SimpleNamespace as Obj
from unittest.mock import Mock

import httpx
import pytest

from app.services import user_contribution_service as service


def user(identifier="user-a"):
    return Obj(id=identifier, auth_provider="clerk", external_auth_id="clerk-a")


def payload(days=None, github_id=42, total=1):
    return {"data": {"viewer": {"databaseId": github_id, "login": "verified-person",
        "contributionsCollection": {"contributionCalendar": {"totalContributions": total,
            "weeks": [{"contributionDays": days if days is not None else [
                {"date": "2024-02-29", "contributionCount": 1, "contributionLevel": "FIRST_QUARTILE"}]}]}}}}}


def install_clerk(monkeypatch, *, verified=True, provider_id="42", token_id="42", tokens=True):
    account = Obj(id="external-a", provider="oauth_github", provider_user_id=provider_id,
                  verification=Obj(status="verified" if verified else "unverified"))
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=None)
    client.users.get.return_value = Obj(external_accounts=[account])
    client.users.get_o_auth_access_token.return_value = [Obj(external_account_id="external-a", provider_user_id=token_id,
        provider="oauth_github", scopes=["read:user"], token="fixture-user-token")] if tokens else []
    monkeypatch.setattr(service, "Clerk", Mock(return_value=client))
    return client


@pytest.mark.parametrize("verified,token_id,reason", [(False, "42", "identity_unavailable"), (True, "99", "user_access_unavailable")])
def test_only_verified_link_and_matching_user_token_are_accepted(monkeypatch, verified, token_id, reason):
    client = install_clerk(monkeypatch, verified=verified, token_id=token_id)
    assert service._existing_access(user()) == (None, reason)
    if not verified:
        client.users.get_o_auth_access_token.assert_not_called()


def test_existing_clerk_token_is_server_only_and_context_changes_with_access(monkeypatch):
    client = install_clerk(monkeypatch)
    first, reason = service._existing_access(user())
    assert reason is None and first[:2] == ("42", "fixture-user-token")
    assert len(first[2]) == 64 and "fixture-user-token" not in first[2]
    assert client.users.get.call_args.kwargs["user_id"] == "clerk-a"
    assert client.users.get_o_auth_access_token.call_args.kwargs["paginated"] is False
    client.users.get_o_auth_access_token.return_value[0].token = "rotated-user-token"
    assert service._existing_access(user())[0][2] != first[2]
    client.users.get.return_value = Obj(external_accounts=[])
    assert service._existing_access(user()) == (None, "identity_unavailable")


def test_calendar_dates_counts_and_private_viewer_identity_are_not_inferred():
    result = service._parse(payload(), "42", 2024, date(2026, 1, 1))
    assert result["days"] == [{"date": "2024-02-29", "count": 1, "level": 1}]
    assert result["total"] == 1 and result["login"] == "verified-person"
    with pytest.raises(ValueError): service._parse(payload(github_id=99), "42", 2024, date(2026, 1, 1))
    with pytest.raises(ValueError): service._parse({"errors": [{"message": "private access denied"}]}, "42", 2024, date(2026, 1, 1))
    with pytest.raises(ValueError): service._parse(payload(total=5), "42", 2024, date(2026, 1, 1))
    repeated = payload()["data"]["viewer"]["contributionsCollection"]["contributionCalendar"]["weeks"][0]["contributionDays"] * 2
    with pytest.raises(ValueError): service._parse(payload(days=repeated, total=2), "42", 2024, date(2026, 1, 1))
    boundary = [{"date": day, "contributionCount": count, "contributionLevel": "FIRST_QUARTILE"}
                for day, count in [("2025-12-31", 5), ("2026-01-01", 1), ("2026-01-02", 2)]]
    assert service._parse(payload(days=boundary), "42", 2026, date(2026, 1, 1))["days"] == [
        {"date": "2026-01-01", "count": 1, "level": 1}]


@pytest.mark.asyncio
async def test_query_uses_exact_viewer_and_year_bounds_with_user_year_context_cache(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(service, "time", Obj(monotonic=lambda: clock[0]))
    context = ["context-a"]
    check = Mock(side_effect=lambda target: (("42", "fixture-user-token", context[0]), None))
    monkeypatch.setattr(service, "_existing_access", check)
    requests = []
    original_client = httpx.AsyncClient

    async def respond(request):
        import json
        requests.append(json.loads(request.content))
        await asyncio.sleep(0)
        return httpx.Response(200, json=payload() if "2024" in requests[-1]["variables"]["from"] else payload(days=[], total=0), request=request)

    monkeypatch.setattr(service.httpx, "AsyncClient", lambda **kwargs: original_client(**kwargs, transport=httpx.MockTransport(respond)))
    first, second = await asyncio.gather(service.get_user_contributions(user(), 2024), service.get_user_contributions(user(), 2024))
    assert first == second and len(requests) == 1 and check.call_count == 2
    assert requests[0] == {"query": service.CALENDAR_QUERY, "variables": {"from": "2024-01-01T00:00:00Z", "to": "2024-12-31T23:59:59Z"}}
    assert "viewer" in service.CALENDAR_QUERY and "organizationID" not in service.CALENDAR_QUERY
    first["days"].clear()
    assert len((await service.get_user_contributions(user(), 2024))["days"]) == 1
    await service.get_user_contributions(user("user-b"), 2024)
    context[0] = "context-b"
    await service.get_user_contributions(user(), 2024)
    assert len(requests) == 3
    await service.get_user_contributions(user(), 2025)
    assert len(requests) == 4
    clock[0] += 61
    await service.get_user_contributions(user(), 2024)
    assert len(requests) == 5
    check.side_effect = lambda target: (None, "identity_unavailable")
    assert (await service.get_user_contributions(user(), 2024))["status"] == "unavailable"
    assert len(requests) == 5  # A removed identity cannot hit the old successful cache.


@pytest.mark.asyncio
async def test_reads_are_bounded_and_one_cancelled_waiter_does_not_cancel_shared_query(monkeypatch):
    monkeypatch.setattr(service, "_existing_access", lambda target: (("42", "fixture-user-token", "shared"), None))
    original_client = httpx.AsyncClient
    active = 0
    maximum = 0
    gate, started = asyncio.Event(), asyncio.Event()
    async def respond(request):
        nonlocal active, maximum
        active += 1
        maximum = max(active, maximum)
        if active == 4: started.set()
        await gate.wait()
        active -= 1
        return httpx.Response(200, json=payload())
    monkeypatch.setattr(service.httpx, "AsyncClient", lambda **kwargs: original_client(**kwargs, transport=httpx.MockTransport(respond)))
    first = asyncio.create_task(service.get_user_contributions(user(), 2024))
    shared = asyncio.create_task(service.get_user_contributions(user(), 2024))
    others = [asyncio.create_task(service.get_user_contributions(user(f"person-{index}"), 2024)) for index in range(8)]
    await asyncio.wait_for(started.wait(), 2)
    first.cancel()
    with pytest.raises(asyncio.CancelledError): await first
    gate.set()
    assert (await shared)["status"] == "available"
    assert all(item["status"] == "available" for item in await asyncio.gather(*others))
    assert maximum == 4


@pytest.mark.asyncio
async def test_query_failure_does_not_expose_upstream_messages_or_replace_personal_data(monkeypatch):
    monkeypatch.setattr(service, "_existing_access", lambda target: (("42", "fixture-user-token", "failure"), None))
    original_client = httpx.AsyncClient
    monkeypatch.setattr(service.httpx, "AsyncClient", lambda **kwargs: original_client(**kwargs,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"errors": [{"message": "sensitive upstream detail"}]}))))
    result = await service.get_user_contributions(user(), 2024)
    assert result["status"] == "unavailable" and result["total"] is None and result["days"] == []
    assert "sensitive" not in str(result) and "fixture-user-token" not in str(result)


@pytest.mark.asyncio
async def test_current_query_ends_at_current_instant_and_rejects_future_year(monkeypatch):
    class Clock:
        @staticmethod
        def now(zone): return datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(service, "datetime", Clock)
    monkeypatch.setattr(service, "_existing_access", lambda target: (("42", "fixture-user-token", "current"), None))
    original_client = httpx.AsyncClient
    async def respond(request):
        import json
        assert json.loads(request.content)["variables"] == {"from": "2026-01-01T00:00:00Z", "to": "2026-01-01T12:00:00+00:00"}
        return httpx.Response(200, json=payload(days=[], total=0))
    monkeypatch.setattr(service.httpx, "AsyncClient", lambda **kwargs: original_client(**kwargs, transport=httpx.MockTransport(respond)))
    assert (await service.get_user_contributions(user(), 2026))["total"] == 0
    with pytest.raises(ValueError): await service.get_user_contributions(user(), 2027)
