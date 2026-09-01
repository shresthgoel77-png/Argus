import logging

from sqlalchemy.orm import Session

from app.investigation.git_evidence import PROJECT_ROOT, collect_git_evidence
from app.investigation.hypotheses import generate_hypotheses
from app.investigation.logs_evidence import collect_logs_evidence
from app.investigation.metrics_evidence import collect_metrics_evidence
from app.investigation.razorpay_evidence import collect_razorpay_evidence
from app.investigation.timeline import build_timeline
from app.models import Evidence, Incident

logger = logging.getLogger(__name__)

def _record_collection_error(
    incident: Incident, db_session: Session, collector: str, error: Exception
) -> Evidence:
    evidence = Evidence(
        incident_id=incident.id,
        category="collection_error",
        content={"collector": collector, "error": str(error)},
    )
    db_session.add(evidence)
    db_session.commit()
    db_session.refresh(evidence)
    return evidence


def _evidence_payload(evidence: Evidence) -> dict:
    return {"id": evidence.id, "category": evidence.category, **(evidence.content or {})}


def run_investigation(incident_id: int, db_session: Session) -> dict:
    """Collect factual evidence, then derive explicitly-labelled correlations."""
    incident = db_session.query(Incident).filter(Incident.id == incident_id).first()
    if incident is None:
        raise ValueError(f"Incident {incident_id} not found")

    incident.status = "investigating"
    db_session.commit()
    db_session.refresh(incident)

    collected_evidence: list[Evidence] = []
    collectors = [
        ("metrics", lambda: collect_metrics_evidence(incident, db_session)),
        ("logs", lambda: collect_logs_evidence(incident, db_session)),
        (
            "git",
            lambda: collect_git_evidence(incident, db_session, repo_path=PROJECT_ROOT),
        ),
    ]
    for collector_name, collector in collectors:
        try:
            collected = collector()
            if isinstance(collected, list):
                collected_evidence.extend(collected)
            else:
                collected_evidence.append(collected)
        except Exception as error:
            logger.exception("%s evidence collection failed for incident %s", collector_name, incident.id)
            collected_evidence.append(
                _record_collection_error(incident, db_session, collector_name, error)
            )

    if incident.type == "webhook_failure":
        try:
            collected = collect_razorpay_evidence(incident, db_session)
            collected_evidence.extend(collected)
        except Exception as error:
            logger.exception("razorpay evidence collection failed for incident %s", incident.id)
            collected_evidence.append(
                _record_collection_error(incident, db_session, "razorpay", error)
            )

    hypotheses = generate_hypotheses(incident, collected_evidence, db_session)
    timeline = build_timeline(incident, collected_evidence)

    # This engine intentionally does not emit a conclusion or root-cause field.
    # Root-cause determination belongs to the Phase 5 AI reasoning layer; adding a
    # conclusion here would present a hypothesis as fact and violate that boundary.
    incident.status = "investigated"
    db_session.commit()

    observed_facts = [
        _evidence_payload(evidence)
        for evidence in collected_evidence
        if evidence.category == "observed_fact"
    ]
    return {
        "incident_id": incident.id,
        "observed_facts": observed_facts,
        "correlations": timeline,
        "hypotheses": [_evidence_payload(evidence) for evidence in hypotheses],
        "evidence_ids": [
            evidence.id for evidence in [*collected_evidence, *hypotheses] if evidence.id is not None
        ],
    }
