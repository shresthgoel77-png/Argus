from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from app.services import user_contribution_service as service


@pytest.mark.asyncio
async def test_personal_calendar_requires_existing_auth(async_client, monkeypatch):
    read = AsyncMock()
    monkeypatch.setattr(service, "get_user_contributions", read)
    assert (await async_client.get("/api/v1/github/contributions?year=2024")).status_code == 401
    read.assert_not_called()


@pytest.mark.asyncio
async def test_personal_calendar_does_not_accept_another_user(authorized_client, test_user, monkeypatch):
    read = AsyncMock(return_value=service.unavailable(2024, "identity_unavailable", datetime.now(timezone.utc).date()))
    monkeypatch.setattr(service, "get_user_contributions", read)
    response = await authorized_client.get("/api/v1/github/contributions?year=2024&user_id=someone-else&login=untrusted")
    assert response.status_code == 200 and response.headers["cache-control"] == "private, no-store"
    assert read.call_args.args[0].id == test_user.id and read.call_args.args[1] == 2024
    assert response.json()["total"] is None and response.json()["days"] == []


@pytest.mark.asyncio
async def test_year_validation_prevents_unsupported_queries(authorized_client, monkeypatch):
    read = AsyncMock()
    monkeypatch.setattr(service, "get_user_contributions", read)
    for query in ["year=2007", "year=not-a-year", f"year={datetime.now(timezone.utc).year + 1}", ""]:
        assert (await authorized_client.get(f"/api/v1/github/contributions?{query}")).status_code == 422
    read.assert_not_called()
