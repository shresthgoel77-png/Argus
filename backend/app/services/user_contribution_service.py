"""Personal calendar reads using only an existing verified Clerk GitHub OAuth link."""
from __future__ import annotations

import asyncio
import copy
import hashlib
import time
from collections import OrderedDict
from datetime import date, datetime, timezone
from weakref import WeakKeyDictionary

import httpx
from clerk_backend_api import Clerk
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.models.user import User

CALENDAR_QUERY = """query PersonalCalendar($from: DateTime!, $to: DateTime!) {
  viewer {
    databaseId login
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel } }
      }
    }
  }
}"""
_caches: WeakKeyDictionary = WeakKeyDictionary()
_LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
           "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


def unavailable(year: int, reason: str, today: date) -> dict:
    return {"status": "unavailable", "year": year, "as_of_date": today.isoformat(),
            "reason": reason, "days": [], "total": None, "access_context": None}


def _existing_access(user: User):
    """Recheck the current link/token before consulting calendar cache. Never log tokens."""
    if user.auth_provider != "clerk" or not user.external_auth_id or not settings.clerk_secret_key:
        return None, "identity_unavailable"
    with Clerk(bearer_auth=settings.clerk_secret_key.get_secret_value()) as clerk:
        identity = clerk.users.get(user_id=user.external_auth_id, timeout_ms=10000)
        linked = [account for account in identity.external_accounts
                  if account.provider in {"github", "oauth_github"}
                  and getattr(getattr(account, "verification", None), "status", None) == "verified"
                  and str(account.provider_user_id).isdigit()]
        if len(linked) != 1:
            return None, "identity_unavailable"
        account = linked[0]
        tokens = clerk.users.get_o_auth_access_token(
            user_id=user.external_auth_id, provider="oauth_github", paginated=False, timeout_ms=10000)
        matching = [token for token in tokens
                    if token.external_account_id == account.id
                    and str(token.provider_user_id) == str(account.provider_user_id)
                    and token.provider in {"github", "oauth_github"} and token.token]
        if len(matching) != 1:
            return None, "user_access_unavailable"
        token = matching[0]
        # Hashes are cache discriminators, never a substitute for verified identity.
        context = hashlib.sha256(repr((str(user.id), user.external_auth_id, account.id,
            str(account.provider_user_id), sorted(token.scopes or []), token.token)).encode()).hexdigest()
        return (str(account.provider_user_id), token.token, context), None


def _parse(payload: dict, github_id: str, year: int, today: date) -> dict:
    if payload.get("errors"):
        raise ValueError("GraphQL access or query failure")
    viewer = payload["data"]["viewer"]
    if str(viewer["databaseId"]) != github_id or not isinstance(viewer["login"], str):
        raise ValueError("GitHub viewer does not match the verified linked user")
    calendar = viewer["contributionsCollection"]["contributionCalendar"]
    total = calendar["totalContributions"]
    if type(total) is not int or total < 0:
        raise ValueError("Invalid calendar total")
    days = {}
    for week in calendar["weeks"]:
        for item in week["contributionDays"]:
            day = date.fromisoformat(item["date"])
            if day.isoformat() != item["date"]:
                raise ValueError("Invalid date")
            if day.year != year or day > today:
                continue  # Upstream week padding/future buckets are not selected-year data.
            count, level = item["contributionCount"], item["contributionLevel"]
            if day in days or type(count) is not int or count < 0 or level not in _LEVELS:
                raise ValueError("Invalid or duplicate contribution day")
            if (count == 0) != (level == "NONE"):
                raise ValueError("Inconsistent contribution level")
            days[day] = {"date": day.isoformat(), "count": count, "level": _LEVELS[level]}
    if sum(item["count"] for item in days.values()) != total:
        raise ValueError("Calendar total does not match selected date buckets")
    return {"status": "available", "year": year, "as_of_date": today.isoformat(),
            "github_user_id": github_id, "login": viewer["login"], "total": total,
            "days": [days[day] for day in sorted(days)]}


async def get_user_contributions(user: User, year: int) -> dict:
    now = datetime.now(timezone.utc)
    today = now.date()
    if not 2008 <= year <= today.year:
        raise ValueError("Unsupported calendar year")
    try:
        access, reason = await run_in_threadpool(_existing_access, user)
    except Exception:
        return unavailable(year, "identity_check_failed", today)
    if access is None:
        return unavailable(year, reason, today)
    github_id, token, context = access
    loop = asyncio.get_running_loop()
    cache = _caches.setdefault(loop, {"values": OrderedDict(), "pending": {}, "semaphore": asyncio.Semaphore(4)})
    key = (str(user.id), year, context, today)
    cached = cache["values"].get(key)
    if cached and cached[0] > time.monotonic():
        cache["values"].move_to_end(key)
        return copy.deepcopy(cached[1])

    async def read():
        try:
            async with cache["semaphore"]:
                try:
                    async with httpx.AsyncClient(base_url="https://api.github.com", timeout=10) as client:
                        response = await client.post("/graphql", headers={"Authorization": f"Bearer {token}"},
                            json={"query": CALENDAR_QUERY, "variables": {
                                "from": f"{year}-01-01T00:00:00Z",
                                "to": now.isoformat() if year == today.year else f"{year}-12-31T23:59:59Z"}})
                        response.raise_for_status()
                        result = _parse(response.json(), github_id, year, today)
                        result["access_context"] = context
                except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
                    result = unavailable(year, "calendar_access_failed", today)
            cache["values"][key] = (time.monotonic() + (60 if result["status"] == "available" else 15), result)
            cache["values"].move_to_end(key)
            while len(cache["values"]) > 128:
                cache["values"].popitem(last=False)
            return result
        finally:
            cache["pending"].pop(key, None)

    if key not in cache["pending"]:
        cache["pending"][key] = asyncio.create_task(read())
    return copy.deepcopy(await asyncio.shield(cache["pending"][key]))
