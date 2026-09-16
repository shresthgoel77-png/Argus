from datetime import datetime, timedelta, timezone

import pytest

from tests.integration.conftest import *  # noqa: F401,F403

from app.core.exceptions import AppError
from app.integrations.ai.exceptions import (
    AIProviderInvalidResponseError,
    AIProviderRateLimitedError,
    AIProviderUnavailableError,
    InvalidAPIKeyError,
)
from app.integrations.ai.provider_base import StructuredAnalysisResult
from app.models.ai_analysis import AIAnalysis
from app.models.ai_connection import AIConnection
from app.models.finding import Finding
from app.services import ai_analysis_service


API_KEY = "AIza-analysis-test-key-that-must-not-leak"


def make_finding(db_session, test_user_repository):
    finding = Finding(
        repository_id=test_user_repository.id,
        category="security",
        type="vulnerability",
        title="Unsafe finding",
        description="A finding to analyze.",
        severity="high",
        status="open",
        source="test",
        evidence={},
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)
    return finding


def add_connection(db_session, test_user, *, status="valid"):
    connection = AIConnection(
        user_id=test_user.id,
        provider="mock",
        model="mock-model",
        encrypted_api_key="encrypted-key",
        status=status,
    )
    db_session.add(connection)
    db_session.commit()
    db_session.refresh(connection)
    return connection


class StubProvider:
    def __init__(self, *, api_key, db_session, result=None, error=None):
        assert api_key == API_KEY
        self.db_session = db_session
        self.result = result
        self.error = error

    def generate_analysis(self, context):
        assert self.db_session.query(AIAnalysis).count() == 1
        assert self.db_session.query(AIAnalysis).one().status == "pending"
        if self.error is not None:
            raise self.error
        return self.result


def patch_provider(monkeypatch, db_session, *, result=None, error=None):
    monkeypatch.setattr(
        ai_analysis_service,
        "get_provider",
        lambda provider_key: lambda **kwargs: StubProvider(
            db_session=db_session,
            result=result,
            error=error,
            **kwargs,
        ),
    )
    monkeypatch.setattr(
        ai_analysis_service.ai_connection_service,
        "get_decrypted_api_key",
        lambda db, user_id: API_KEY,
    )


def test_not_configured_raises_without_persisting_row(
    db_session, test_user, test_user_repository
):
    finding = make_finding(db_session, test_user_repository)

    with pytest.raises(ai_analysis_service.AINotConfiguredError):
        ai_analysis_service.request_finding_analysis(finding, test_user)

    assert db_session.query(AIAnalysis).count() == 0


def test_invalid_connection_status_raises_without_persisting_row(
    db_session, test_user, test_user_repository
):
    finding = make_finding(db_session, test_user_repository)
    add_connection(db_session, test_user, status="error")

    with pytest.raises(ai_analysis_service.AINotConfiguredError):
        ai_analysis_service.request_finding_analysis(finding, test_user)

    assert db_session.query(AIAnalysis).count() == 0


def test_success_persists_completed_analysis(
    db_session, test_user, test_user_repository, monkeypatch
):
    finding = make_finding(db_session, test_user_repository)
    add_connection(db_session, test_user)
    result = StructuredAnalysisResult(
        summary="Explained",
        severity="critical",
        confidence=0.91,
        reasoning_summary="Evidence supports the assessment.",
        recommendations=["Patch the issue"],
    )
    patch_provider(monkeypatch, db_session, result=result)
    monkeypatch.setattr(
        ai_analysis_service.ai_context_builder,
        "build_context",
        lambda current_finding: object(),
    )

    analysis = ai_analysis_service.request_finding_analysis(finding, test_user)

    assert analysis.status == "completed"
    assert analysis.summary == result.summary
    assert analysis.severity_assessment == result.severity
    assert analysis.confidence == result.confidence
    assert analysis.recommendations == result.recommendations
    assert analysis.completed_at is not None
    assert analysis.error_message is None
    assert db_session.query(AIAnalysis).count() == 1


@pytest.mark.parametrize(
    ("provider_error", "expected_code", "expected_message"),
    [
        (
            InvalidAPIKeyError(API_KEY),
            "ai_provider_invalid_api_key",
            "The configured AI provider rejected the API key.",
        ),
        (
            AIProviderRateLimitedError(API_KEY),
            "ai_provider_rate_limited",
            "The AI provider is rate limited.",
        ),
        (
            AIProviderUnavailableError(API_KEY),
            "ai_provider_unavailable",
            "The AI provider is unavailable.",
        ),
        (
            AIProviderInvalidResponseError(API_KEY),
            "ai_provider_invalid_response",
            "The AI provider returned an invalid response.",
        ),
    ],
)
def test_provider_failure_persists_sanitized_failed_analysis(
    db_session,
    test_user,
    test_user_repository,
    monkeypatch,
    provider_error,
    expected_code,
    expected_message,
):
    finding = make_finding(db_session, test_user_repository)
    add_connection(db_session, test_user)
    patch_provider(monkeypatch, db_session, error=provider_error)
    monkeypatch.setattr(
        ai_analysis_service.ai_context_builder,
        "build_context",
        lambda current_finding: object(),
    )

    with pytest.raises(AppError) as caught:
        ai_analysis_service.request_finding_analysis(finding, test_user)

    analysis = db_session.query(AIAnalysis).one()
    assert analysis.status == "failed"
    assert analysis.error_message == expected_message
    assert API_KEY not in analysis.error_message
    assert analysis.completed_at is not None
    assert caught.value.code == expected_code
    assert caught.value.message == expected_message
    assert API_KEY not in str(caught.value)


def test_unexpected_failure_is_sanitized_and_persisted(
    db_session, test_user, test_user_repository, monkeypatch
):
    finding = make_finding(db_session, test_user_repository)
    add_connection(db_session, test_user)
    unexpected = RuntimeError(API_KEY)
    patch_provider(monkeypatch, db_session, error=unexpected)
    monkeypatch.setattr(
        ai_analysis_service.ai_context_builder,
        "build_context",
        lambda current_finding: object(),
    )

    with pytest.raises(ai_analysis_service.AIAnalysisFailedError) as caught:
        ai_analysis_service.request_finding_analysis(finding, test_user)

    analysis = db_session.query(AIAnalysis).one()
    assert analysis.status == "failed"
    assert analysis.error_message == "The AI analysis could not be completed."
    assert API_KEY not in analysis.error_message
    assert API_KEY not in str(caught.value)


def test_latest_and_list_analysis_are_ordered_and_paginated(
    db_session, test_user, test_user_repository
):
    finding = make_finding(db_session, test_user_repository)
    requested_at = datetime.now(timezone.utc)
    for index, summary in enumerate(("first", "second")):
        db_session.add(
            AIAnalysis(
                finding_id=finding.id,
                provider="mock",
                model="mock-model",
                status="completed",
                summary=summary,
                requested_at=requested_at + timedelta(seconds=index),
            )
        )
        db_session.commit()

    latest = ai_analysis_service.get_latest_analysis(finding)
    total, items = ai_analysis_service.list_analyses(finding, limit=1)

    assert latest is not None
    assert latest.summary == "second"
    assert total == 2
    assert len(items) == 1
    assert items[0].summary == "second"
