from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import settings
from app.main import app
from app.services.scheduled_monitoring_service import GlobalRunSummary

ENDPOINT = "/api/v1/internal/scheduled-monitoring/run"


def test_scheduler_secret_is_required_and_does_not_run_cycle(monkeypatch, caplog):  # noqa: E501
    monkeypatch.setattr(
        settings,
        "scheduler_shared_secret",
        SecretStr("test-secret"),
    )
    cycle = AsyncMock()

    with patch(
        "app.api.v1.internal.run_scheduled_monitoring_cycle",
        cycle,
    ), TestClient(app) as client:
        missing = client.post(ENDPOINT)
        incorrect = client.post(
            ENDPOINT,
            headers={"X-Scheduler-Secret": "wrong-secret"},
        )

    assert missing.status_code == 401
    assert "test-secret" not in missing.text

    assert incorrect.status_code == 401
    assert "test-secret" not in incorrect.text

    assert "test-secret" not in caplog.text

    cycle.assert_not_awaited()


def test_scheduler_secret_runs_cycle_and_returns_safe_summary(monkeypatch, caplog):  # noqa: E501
    monkeypatch.setattr(
        settings,
        "scheduler_shared_secret",
        SecretStr("test-secret"),
    )
    summary = GlobalRunSummary(
        correlation_id="run-123",
        attempted=3,
        succeeded=2,
        partially_failed=1,
        total_duration=1.25,
    )

    with patch(
        "app.api.v1.internal.run_scheduled_monitoring_cycle",
        new=AsyncMock(return_value=summary),
    ) as cycle, TestClient(app) as client:
        response = client.post(
            ENDPOINT,
            headers={"X-Scheduler-Secret": "test-secret"},
        )

    assert response.status_code == 200

    # Verify the secret is not in the response or logs
    assert "test-secret" not in response.text
    assert "test-secret" not in caplog.text

    # Verify only approved fields are present
    response_json = response.json()
    approved_keys = {
        "correlation_id",
        "attempted",
        "succeeded",
        "partially_failed",
        "fully_failed",
        "skipped",
        "total_duration",
    }
    assert set(response_json.keys()) == approved_keys

    # Ensure no repository-level details are present
    response_str = response.text.lower()
    assert "repository" not in response_str
    assert "repo" not in response_str
    assert "content" not in response_str

    assert response_json == {
        "correlation_id": "run-123",
        "attempted": 3,
        "succeeded": 2,
        "partially_failed": 1,
        "fully_failed": 0,
        "skipped": 0,
        "total_duration": 1.25,
    }
    cycle.assert_awaited_once()


def test_scheduler_route_is_excluded_from_public_schema():
    schema = TestClient(app).get("/openapi.json").json()

    assert ENDPOINT not in schema["paths"]


def test_production_requires_scheduler_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SCHEDULER_SHARED_SECRET", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")

    from app.core.config import Settings

    try:
        Settings(_env_file=None)
    except ValueError as exc:
        assert "SCHEDULER_SHARED_SECRET" in str(exc)
    else:
        raise AssertionError("Production settings accepted missing scheduler secret")  # noqa: E501
