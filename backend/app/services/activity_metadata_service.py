"""Read-only Activity metadata. No issue/PR lists, public-token fallback, or DB writes."""
from __future__ import annotations

import asyncio
import copy
import re
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote
from weakref import WeakKeyDictionary

from app.integrations.github.client import GitHubAppClient
from app.integrations.github.exceptions import GitHubAPIError

_TTL = 60
_ERROR_TTL = 15
_CACHE_LIMIT = 256
_CONCURRENCY = 4


def unavailable_metadata(repository_id: str) -> dict[str, Any]:
    return {
        "repository_id": repository_id,
        "metadata_status": "unavailable",
        "primary_language_status": "unknown",
        "primary_language": None,
        "description": None, "topics": None,
        "stars": None, "forks": None,
        "open_issues_and_pull_requests": None,
        "updated_at": None,
        "languages_status": "unavailable", "language_bytes": None,
        "metadata_error": None, "languages_error": None,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def _count(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _path(full_name: str) -> str:
    parts = full_name.split("/")
    if (len(parts) != 2 or not re.fullmatch(r"[A-Za-z0-9-]+", parts[0])
            or not re.fullmatch(r"[A-Za-z0-9_.-]+", parts[1])
            or parts[1] in {".", ".."}):
        raise ValueError("Invalid saved repository name")
    return "/repos/" + "/".join(quote(part, safe="") for part in parts)


class ActivityMetadataClient(GitHubAppClient):
    """Uses the existing installation authentication, timeout, and error mapping."""

    async def read_metadata(self, repository_id: str, full_name: str, github_id: int) -> dict[str, Any]:
        result = unavailable_metadata(repository_id)
        try:
            path = _path(full_name)
            response = await self._request("GET", path)
            data = response.json()
            # Never return metadata for a repository that merely reused a saved name.
            if not isinstance(data, dict) or data.get("id") != github_id:
                raise ValueError("Repository identity mismatch")
            language = data.get("language")
            result.update(
                metadata_status="available",
                primary_language=language if isinstance(language, str) and language.strip() else None,
                primary_language_status=("known" if isinstance(language, str) and language.strip()
                                         else "none" if "language" in data and language is None else "unknown"),
                description=data.get("description") if isinstance(data.get("description"), str) else None,
                topics=data["topics"] if isinstance(data.get("topics"), list)
                and all(isinstance(topic, str) for topic in data["topics"]) else None,
                stars=_count(data.get("stargazers_count")),
                forks=_count(data.get("forks_count")),
                # GitHub's REST repository counter includes open pull requests.
                open_issues_and_pull_requests=_count(data.get("open_issues_count")),
                updated_at=data.get("updated_at") if isinstance(data.get("updated_at"), str) else None,
            )
        except (GitHubAPIError, ValueError, TypeError) as exc:
            result["metadata_error"] = exc.code if isinstance(exc, GitHubAPIError) else "invalid_metadata"
            return result

        try:
            response = await self._request("GET", f"{path}/languages")
            languages = response.json()
            # This endpoint is an unpaginated byte map. Fail closed if GitHub ever
            # advertises continuation rather than presenting a first page as complete.
            if ("next" in response.links or not isinstance(languages, dict)
                    or any(not name or _count(size) is None for name, size in languages.items())):
                raise ValueError("Incomplete or invalid language bytes")
            result.update(languages_status="available", language_bytes=languages)
        except (GitHubAPIError, ValueError, TypeError) as exc:
            result["languages_error"] = exc.code if isinstance(exc, GitHubAPIError) else "invalid_languages"
        return result


@dataclass
class _ReadCache:
    # One semaphore per event loop, shared by this endpoint's requests/users.
    semaphore: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(_CONCURRENCY))
    values: OrderedDict = field(default_factory=OrderedDict)
    pending: dict[tuple, asyncio.Task] = field(default_factory=dict)


_caches: WeakKeyDictionary = WeakKeyDictionary()


async def get_activity_metadata(*, user_id: str, repository_id: str, connection_id: str,
                                installation_id: int, github_id: int, full_name: str) -> dict[str, Any]:
    """Call only AFTER current DB ownership/connection checks, including cache hits."""
    loop = asyncio.get_running_loop()
    cache = _caches.setdefault(loop, _ReadCache())
    key = (user_id, repository_id, connection_id, installation_id, github_id, full_name)
    cached = cache.values.get(key)
    if cached and cached[0] > time.monotonic():
        cache.values.move_to_end(key)
        return copy.deepcopy(cached[1])

    async def load() -> dict[str, Any]:
        try:
            async with cache.semaphore:
                try:
                    async with ActivityMetadataClient(installation_id=installation_id) as client:
                        result = await asyncio.wait_for(client.read_metadata(repository_id, full_name, github_id), 25)
                except (GitHubAPIError, TimeoutError):
                    result = unavailable_metadata(repository_id)
                    result["metadata_error"] = "metadata_unavailable"
            ttl = _TTL if (result["primary_language_status"] != "unknown"
                           and result["languages_status"] == "available") else _ERROR_TTL
            cache.values[key] = (time.monotonic() + ttl, result)
            cache.values.move_to_end(key)
            while len(cache.values) > _CACHE_LIMIT:
                cache.values.popitem(last=False)
            return result
        finally:
            cache.pending.pop(key, None)

    if key not in cache.pending:
        cache.pending[key] = asyncio.create_task(load())
    # A disconnected caller cannot cancel a request shared with another caller.
    return copy.deepcopy(await asyncio.shield(cache.pending[key]))
