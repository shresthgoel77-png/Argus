"""Bounded, installation-authenticated default-branch history; never an all-time total."""
from __future__ import annotations

import asyncio
import copy
import hashlib
import re
import time
import uuid
from collections import OrderedDict
from datetime import date, datetime, time as day_time, timedelta, timezone
from weakref import WeakKeyDictionary

from app.integrations.github.client import GitHubAppClient
from app.integrations.github.exceptions import GitHubAPIError
from app.services.activity_metadata_service import _path

MAX_PAGES = 5
PAGE_SIZE = 100
_caches: WeakKeyDictionary = WeakKeyDictionary()
HISTORY_QUERY = """query RepositoryContributions($owner: String!, $name: String!,
  $expression: String!, $after: String, $since: GitTimestamp!, $until: GitTimestamp!) {
  repository(owner: $owner, name: $name) {
    databaseId isEmpty
    object(expression: $expression) { ... on Commit {
      oid history(first: 100, after: $after, since: $since, until: $until) {
        pageInfo { hasNextPage endCursor }
        nodes { oid message committedDate authoredDate url additions deletions
          author { name email user { databaseId login } } }
      }
    } }
  }
}"""


class ContributionCursorError(ValueError):
    """The bounded in-process snapshot is missing, expired, or not this scope."""


def contribution_range(start: date | None, end: date | None, today: date) -> tuple[date, date]:
    end = end or today
    start = start or end - timedelta(days=89)
    if (start > end or (end - start).days >= 90 or end > min(today, date(2099, 12, 13))
            or start < date(1970, 1, 1)):
        raise ValueError("Use a past or current UTC date range of 1 through 90 days")
    return start, end


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp requires an offset")
    return parsed.astimezone(timezone.utc)


def _count(value):
    return value if type(value) is int and value >= 0 else None


def _event(node: dict, branch: str, since: datetime, until: datetime) -> tuple[dict, str | None]:
    sha = node["oid"]
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40,64}", sha):
        raise ValueError("Invalid commit identity")
    committed = _timestamp(node["committedDate"])
    if not since <= committed <= until:
        raise ValueError("Commit outside requested range")
    author = node.get("author") or {}
    user = author.get("user") or {}
    identity = None
    if type(user.get("databaseId")) is int and user["databaseId"] > 0:
        identity = f"github:{user['databaseId']}"
    elif isinstance(author.get("email"), str) and author["email"].strip():
        # Only used for aggregation; neither email nor this hash leaves the service.
        identity = "email:" + hashlib.sha256(author["email"].strip().casefold().encode()).hexdigest()
    url = node.get("url")
    if not isinstance(url, str) or not url.startswith("https://github.com/"):
        url = None
    return {
        "sha": sha, "message": node.get("message") if isinstance(node.get("message"), str) else None,
        "author": {"name": author.get("name") if isinstance(author.get("name"), str) else None,
                   "login": user.get("login") if isinstance(user.get("login"), str) else None},
        "committed_at": committed.isoformat(),
        "authored_at": _timestamp(node["authoredDate"]).isoformat() if node.get("authoredDate") else None,
        "html_url": url, "branch": branch, "pull_request": None,
        "additions": _count(node.get("additions")), "deletions": _count(node.get("deletions")),
    }, identity


def _aggregate(result: dict, events: dict, start: date, end: date) -> dict:
    records = sorted(events.values(), key=lambda pair: (pair[0]["committed_at"], pair[0]["sha"]), reverse=True)
    result["events"] = [pair[0] for pair in records]
    if result["status"] not in {"available", "partial"}:
        result.update(metrics=None, frequency=[])
        return result
    items = result["events"]
    known = {pair[1] for pair in records if pair[1] is not None}
    unknown = sum(pair[1] is None for pair in records)
    lines_known = all(item["additions"] is not None and item["deletions"] is not None for item in items)
    if not lines_known or unknown:
        result.update(status="partial", reason=result["reason"] or "incomplete_commit_fields")
    result["metrics"] = {
        "commit_count": len(items),
        "additions": sum(item["additions"] for item in items) if lines_known else None,
        "deletions": sum(item["deletions"] for item in items) if lines_known else None,
        "distinct_authors": len(known) if not unknown else None,
        "known_authors": len(known), "unknown_author_commits": unknown,
    }
    buckets = {(start + timedelta(days=offset)).isoformat(): 0 for offset in range((end - start).days + 1)}
    for item in items:
        buckets[item["committed_at"][:10]] += 1
    # A partial bucket is a count within the retrieved subset, never proof of a zero day.
    result["frequency"] = [{"date": day, "commits": count} for day, count in buckets.items()]
    return result


class RepositoryContributionClient(GitHubAppClient):
    async def __aenter__(self):
        await super().__aenter__()
        self._retry_delay = None
        self._rate_limited = False
        self._http.event_hooks["response"].append(self._observe_response)
        return self

    async def _observe_response(self, response):
        # Preserve rate-limit metadata locally without changing the shared client/errors.
        delay = response.headers.get("retry-after")
        remaining = response.headers.get("x-ratelimit-remaining")
        self._rate_limited = response.status_code == 429 or delay is not None or remaining == "0"
        self._retry_delay = None
        if self._rate_limited:
            try:
                self._retry_delay = max(60, int(delay) if delay else
                    int(response.headers["x-ratelimit-reset"]) - int(time.time()))
            except (KeyError, ValueError):
                self._retry_delay = 60

    async def read_contributions(self, repository_id: str, full_name: str, github_id: int,
                                 start: date, end: date) -> dict:
        now = datetime.now(timezone.utc)
        since = datetime.combine(start, day_time.min, timezone.utc)
        until = min(datetime.combine(end, day_time.max, timezone.utc), now)
        result = {"repository_id": repository_id, "status": "unavailable", "reason": None,
                  "retry_after_seconds": None, "snapshot_id": uuid.uuid4().hex,
                  "fetched_at": now.isoformat(), "history_complete": False,
                  "scope": {"start_date": start.isoformat(), "end_date": end.isoformat(),
                            "since": since.isoformat(), "until": until.isoformat(), "timezone": "UTC",
                            "source": "github_graphql_commit_history", "branch": None, "head_sha": None,
                            "includes_merges": True, "author_coverage": "primary_author",
                            "pull_request_coverage": "unsupported", "max_commits": MAX_PAGES * PAGE_SIZE,
                            "aggregation": "retrieved_unique_commits"}}
        events = {}
        try:
            path = _path(full_name)
            metadata = (await self._request("GET", path)).json()
            if type(metadata.get("id")) is not int or metadata["id"] != github_id:
                raise ValueError("Repository identity mismatch")
            branch = metadata.get("default_branch")
            if not isinstance(branch, str) or not branch:
                raise ValueError("Default branch unavailable")
            result["scope"]["branch"] = branch
            owner, name = full_name.split("/")
            expression, after = f"refs/heads/{branch}", None
            seen_cursors = set()
            for _ in range(MAX_PAGES):
                response = await self._request("POST", "/graphql", json={"query": HISTORY_QUERY, "variables": {
                    "owner": owner, "name": name, "expression": expression, "after": after,
                    "since": since.isoformat(), "until": until.isoformat()}})
                if response.status_code in {202, 204}:
                    result.update(status="partial" if events else "pending" if response.status_code == 202 else "unsupported",
                                  reason="provider_pending" if response.status_code == 202 else "provider_no_content",
                                  retry_after_seconds=30 if response.status_code == 202 else None)
                    break
                payload = response.json()
                if payload.get("errors"):
                    codes = {error.get("type") for error in payload["errors"] if isinstance(error, dict)}
                    reason = "rate_limited" if "RATE_LIMITED" in codes else "permission_denied" if "FORBIDDEN" in codes else "graphql_unavailable"
                    result.update(status="partial" if events else "unavailable", reason=reason,
                                  retry_after_seconds=(getattr(self, "_retry_delay", None) or 60) if reason == "rate_limited" else None)
                    break  # Never silently accept data accompanied by GraphQL errors.
                repo = payload["data"]["repository"]
                if type(repo["databaseId"]) is not int or repo["databaseId"] != github_id:
                    raise ValueError("Repository identity mismatch")
                if repo.get("isEmpty") is True:
                    if events:
                        raise ValueError("Inconsistent empty repository")
                    result.update(status="available", history_complete=True)
                    break
                target = repo["object"]
                head = target["oid"]
                if not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40,64}", head):
                    raise ValueError("Invalid branch head")
                if after is not None and head != expression:
                    raise ValueError("Snapshot head changed")
                expression = head  # Pin subsequent pages against pushes/force pushes.
                result["scope"]["head_sha"] = head
                history = target["history"]
                nodes, page = history["nodes"], history["pageInfo"]
                if not isinstance(nodes, list) or len(nodes) > PAGE_SIZE or type(page["hasNextPage"]) is not bool:
                    raise ValueError("Invalid history page")
                page_events = {}
                for node in nodes:
                    event, identity = _event(node, branch, since, until)
                    pair = (event, identity)
                    existing = page_events.get(event["sha"], events.get(event["sha"]))
                    if existing is not None and existing != pair:
                        raise ValueError("Conflicting duplicate commit")
                    page_events[event["sha"]] = pair
                events.update(page_events)
                result["status"] = "partial"
                if not page["hasNextPage"]:
                    result.update(status="available", history_complete=True)
                    break
                if getattr(self, "_rate_limited", False):
                    result.update(reason="rate_limited", retry_after_seconds=getattr(self, "_retry_delay", None) or 60)
                    break
                after = page["endCursor"]
                if not isinstance(after, str) or not after or after in seen_cursors or not nodes:
                    raise ValueError("Invalid history continuation")
                seen_cursors.add(after)
                result["reason"] = "scan_limit"
            if result["history_complete"]:
                result["reason"] = None
        except GitHubAPIError as exc:
            reason = ("rate_limited" if exc.response_status == 429 or getattr(self, "_rate_limited", False) else "authorization_or_rate_limit"
                      if exc.response_status == 403 else exc.code)
            result.update(status="partial" if events else "unavailable", reason=reason,
                          retry_after_seconds=(getattr(self, "_retry_delay", None) or 60) if exc.response_status in {403, 429} else None)
        except (ValueError, KeyError, TypeError, AttributeError):
            result.update(status="partial" if events else "unavailable", reason="invalid_provider_response")
        return _aggregate(result, events, start, end)


async def get_repository_contributions(*, user_id: str, repository_id: str, connection_id: str,
                                     installation_id: int, github_id: int, full_name: str,
                                     start: date, end: date, cursor: str | None = None, limit: int = 20) -> dict:
    """Caller MUST check current DB ownership before accessing this user-scoped cache."""
    cache = _caches.setdefault(asyncio.get_running_loop(), {
        "values": OrderedDict(), "pending": {}, "semaphore": asyncio.Semaphore(4)})
    key = (user_id, connection_id, installation_id, repository_id, github_id, full_name, start, end)
    cached = cache["values"].get(key)
    offset = 0
    if cursor:
        try:
            snapshot, raw_offset = cursor.split(":")
            offset = int(raw_offset)
            if (not cached or cached[0] <= time.monotonic() or snapshot != cached[1]["snapshot_id"]
                    or offset <= 0 or offset >= len(cached[1]["events"])):
                raise ValueError()
        except (ValueError, KeyError):
            raise ContributionCursorError("Contribution snapshot expired or cursor does not match this scope") from None
    if not cached or cached[0] <= time.monotonic():
        async def load():
            try:
                async with cache["semaphore"]:
                    async with RepositoryContributionClient(installation_id) as client:
                        # Each provider request already has a 10s timeout. Five pages maximum;
                        # no polling, background work, per-commit reads, or automatic retries.
                        result = await client.read_contributions(repository_id, full_name, github_id, start, end)
                ttl = (result["retry_after_seconds"] or (300 if result["status"] == "available"
                       or result["reason"] in {"scan_limit", "incomplete_commit_fields"} else 15))
                cache["values"][key] = (time.monotonic() + ttl, result)
                cache["values"].move_to_end(key)
                while len(cache["values"]) > 128:
                    cache["values"].popitem(last=False)
                return result
            finally:
                cache["pending"].pop(key, None)
        if key not in cache["pending"]:
            cache["pending"][key] = asyncio.create_task(load())
        result = await asyncio.shield(cache["pending"][key])
    else:
        cache["values"].move_to_end(key)
        result = cached[1]
    result = copy.deepcopy(result)
    all_events = result.pop("events")
    result["items"] = all_events[offset:offset + limit]
    next_offset = offset + len(result["items"])
    result["next_cursor"] = f"{result['snapshot_id']}:{next_offset}" if next_offset < len(all_events) else None
    return result
