"""Application service for on-demand finding analyses."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session, object_session

from app.core.exceptions import AppError
from app.integrations.ai import get_provider
from app.integrations.ai.exceptions import (
    AIProviderInvalidResponseError,
    AIProviderRateLimitedError,
    AIProviderUnavailableError,
    InvalidAPIKeyError,
)
from app.models.ai_analysis import AIAnalysis
from app.models.ai_connection import AIConnection
from app.models.finding import Finding
from app.models.user import User
from app.services import ai_connection_service, ai_context_builder


class AINotConfiguredError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="ai_not_configured",
            message="No valid AI connection is configured.",
            status_code=400,
        )


class AIAnalysisFailedError(AppError):
    def __init__(self, *, code: str, message: str, status_code: int) -> None:
        super().__init__(code=code, message=message, status_code=status_code)


_PROVIDER_FAILURES: dict[type[Exception], tuple[str, str, int]] = {
    InvalidAPIKeyError: (
        "ai_provider_invalid_api_key",
        "The configured AI provider rejected the API key.",
        422,
    ),
    AIProviderRateLimitedError: (
        "ai_provider_rate_limited",
        "The AI provider is rate limited.",
        429,
    ),
    AIProviderUnavailableError: (
        "ai_provider_unavailable",
        "The AI provider is unavailable.",
        503,
    ),
    AIProviderInvalidResponseError: (
        "ai_provider_invalid_response",
        "The AI provider returned an invalid response.",
        502,
    ),
}


def _session_for(finding: Finding, user: User) -> Session:
    session = object_session(finding) or object_session(user)
    if session is None:
        raise RuntimeError("The finding or user is not attached to a database session.")
    return session


def _failure_for(exception: Exception) -> AIAnalysisFailedError:
    for exception_type, details in _PROVIDER_FAILURES.items():
        if isinstance(exception, exception_type):
            code, message, status_code = details
            return AIAnalysisFailedError(
                code=code,
                message=message,
                status_code=status_code,
            )
    return AIAnalysisFailedError(
        code="ai_analysis_failed",
        message="The AI analysis could not be completed.",
        status_code=500,
    )


def _persist_failure(db: Session, analysis: AIAnalysis, exception: Exception) -> None:
    mapped = _failure_for(exception)
    analysis.status = "failed"
    analysis.error_message = mapped.message
    analysis.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(analysis)


def request_finding_analysis(finding: Finding, user: User) -> AIAnalysis:
    """Run one observable, on-demand analysis for *finding*."""
    db = _session_for(finding, user)
    connection = (
        db.query(AIConnection)
        .filter(AIConnection.user_id == user.id)
        .first()
    )
    if connection is None or connection.status != "valid":
        raise AINotConfiguredError()

    analysis = AIAnalysis(
        finding_id=finding.id,
        provider=connection.provider,
        model=connection.model,
        status="pending",
        requested_at=datetime.now(timezone.utc),
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    try:
        context = ai_context_builder.build_context(finding)
        provider_class = get_provider(connection.provider)
        provider = provider_class(
            api_key=ai_connection_service.get_decrypted_api_key(db, user.id)
        )
        result = provider.generate_analysis(context)
        analysis.status = "completed"
        analysis.summary = result.summary
        analysis.severity_assessment = result.severity
        analysis.confidence = result.confidence
        analysis.recommendations = result.recommendations
        analysis.error_message = None
        analysis.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(analysis)
        return analysis
    except Exception as exception:
        _persist_failure(db, analysis, exception)
        raise _failure_for(exception) from exception


def get_latest_analysis(finding: Finding) -> AIAnalysis | None:
    db = _session_for(finding, finding.repository)  # type: ignore[arg-type]
    return (
        db.query(AIAnalysis)
        .filter(AIAnalysis.finding_id == finding.id)
        .order_by(desc(AIAnalysis.requested_at))
        .first()
    )


def list_analyses(
    finding: Finding,
    pagination: Any = None,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[int, list[AIAnalysis]]:
    db = _session_for(finding, finding.repository)  # type: ignore[arg-type]
    if pagination is not None:
        limit = getattr(pagination, "limit", limit)
        offset = getattr(pagination, "offset", offset)
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    query = db.query(AIAnalysis).filter(AIAnalysis.finding_id == finding.id)
    total = query.count()
    items = (
        query.order_by(desc(AIAnalysis.requested_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return total, items