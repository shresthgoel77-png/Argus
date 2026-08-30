import datetime
import os

from sqlalchemy.orm import Session, object_session

from app.models import Evidence, Incident


HYPOTHESIS_PROXIMITY_MINUTES = int(os.getenv("HYPOTHESIS_PROXIMITY_MINUTES", "3"))


def _as_utc(value: datetime.datetime) -> datetime.datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc)


def _parse_timestamp(value: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(value).astimezone(datetime.timezone.utc)


def _modifies_runtime_config(changed_files: list[str]) -> bool:
    """Git stat paths can be repository-root-prefixed in a nested worktree."""
    return any(
        path.replace("\\", "/").endswith("simulator/config.json")
        for path in changed_files
    )


def generate_hypotheses(
    incident: Incident,
    evidence_rows: list[Evidence],
    db_session: Session | None = None,
) -> list[Evidence]:
    """Generate only deterministic, explicitly non-factual correlations."""
    db_session = db_session or object_session(incident)
    if db_session is None:
        raise ValueError("A database session is required to persist hypotheses")

    incident_time = _as_utc(incident.timestamp)
    earliest_commit = incident_time - datetime.timedelta(
        minutes=HYPOTHESIS_PROXIMITY_MINUTES
    )
    hypotheses = []

    for evidence in evidence_rows:
        content = evidence.content or {}
        for commit in content.get("commits", []):
            if not _modifies_runtime_config(commit.get("changed_files", [])):
                continue
            try:
                commit_time = _parse_timestamp(commit["timestamp"])
            except (KeyError, TypeError, ValueError):
                continue
            if not earliest_commit <= commit_time <= incident_time:
                continue

            short_sha = commit["sha"][:7]
            hypothesis = Evidence(
                incident_id=incident.id,
                category="hypothesis",
                content={
                    "hypothesis": (
                        f"Commit {short_sha} ('{commit['message']}') is temporally close "
                        "to this incident and modified the application's runtime configuration."
                    ),
                    "confidence": "medium",
                    "supporting_evidence_ids": [evidence.id],
                    "basis": "temporal_proximity_and_file_overlap",
                },
            )
            db_session.add(hypothesis)
            hypotheses.append(hypothesis)

    if hypotheses:
        db_session.commit()
        for hypothesis in hypotheses:
            db_session.refresh(hypothesis)
    return hypotheses
