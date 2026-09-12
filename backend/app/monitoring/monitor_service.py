import uuid
import inspect
from typing import Any, Optional
from sqlalchemy.orm import Session
from app.models.repository import Repository
from app.monitoring.analyzers import get_analyzer
from app.monitoring.analyzer_base import AnalyzerContext
from app.services.finding_service import create_finding
from app.integrations.github.client import GitHubAppClient
from app.schemas.monitoring import MonitorRunResult, FindingSummary
from app.core.logging import get_logger

logger = get_logger(__name__)

async def run_analyzer(
    db: Session,
    analyzer_key: str,
    repository: Repository,
    *,
    normalized_event: Optional[Any] = None
) -> MonitorRunResult:
    if not repository.monitoring_enabled:
        return MonitorRunResult(status="skipped", reason="monitoring_disabled")

    analyzer = get_analyzer(analyzer_key)
    if not analyzer:
        return MonitorRunResult(status="skipped", reason="unknown_analyzer")

    correlation_id = str(uuid.uuid4())
    logger.info(
        "Starting analyzer run",
        extra={
            "repository_id": str(repository.id),
            "analyzer_key": analyzer_key,
            "correlation_id": correlation_id
        }
    )

    try:
        findings_drafts = []
        if analyzer.requires_client:
            installation_id = repository.connection.installation_id
            async with GitHubAppClient(installation_id=installation_id) as code_client:
                context = AnalyzerContext(
                    repository=repository,
                    normalized_event=normalized_event,
                    client=code_client
                )
                res = analyzer.analyze(context)
                if inspect.isawaitable(res):
                    findings_drafts = await res
                else:
                    findings_drafts = res
        else:
            context = AnalyzerContext(
                repository=repository,
                normalized_event=normalized_event,
                client=None
            )
            res = analyzer.analyze(context)
            if inspect.isawaitable(res):
                findings_drafts = await res
            else:
                findings_drafts = res
    except Exception as e:
        logger.error(
            "Analyzer failed with exception",
            exc_info=True,
            extra={
                "repository_id": str(repository.id),
                "analyzer_key": analyzer_key,
                "correlation_id": correlation_id
            }
        )
        return MonitorRunResult(status="failed", error_message=str(e))

    created_findings = []
    source = f"on_demand:{analyzer_key}" if not normalized_event else f"webhook:{normalized_event.event_type}"
    for draft in findings_drafts:
        finding = create_finding(
            db=db,
            repository_id=repository.id,
            category=draft.category,
            type_=draft.type_,
            title=draft.title,
            description=draft.description,
            severity=draft.severity,
            source=source,
            evidence=draft.evidence
        )
        created_findings.append(FindingSummary(
            id=str(finding.id),
            category=finding.category,
            type=finding.type,
            title=finding.title,
            severity=finding.severity
        ))

    logger.info(
        "Analyzer run completed successfully",
        extra={
            "repository_id": str(repository.id),
            "analyzer_key": analyzer_key,
            "correlation_id": correlation_id,
            "findings_count": len(created_findings)
        }
    )
    return MonitorRunResult(status="success", findings_created=created_findings)
