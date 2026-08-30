import datetime
import subprocess
from pathlib import Path

from sqlalchemy.orm import Session

from app.investigation.window import determine_window
from app.models import Evidence, Incident


PROJECT_ROOT = Path(__file__).resolve().parents[3]
GIT_LOG_FORMAT = "%H|%ai|%s"


def _as_utc(value: datetime.datetime) -> datetime.datetime:
    """Treat naive database timestamps as UTC, as the application does elsewhere."""
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc)


def _parse_git_timestamp(value: str) -> datetime.datetime:
    return datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S %z").astimezone(
        datetime.timezone.utc
    )


def _run_git(args: list[str], repo_path: Path) -> str:
    completed = subprocess.run(
        args,
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def _changed_files(sha: str, repo_path: Path) -> list[str]:
    """Extract file paths from git's human-readable --stat output."""
    stat_output = _run_git(["git", "show", "--stat", "--format=", sha, "--"], repo_path)
    changed_files = []
    for line in stat_output.splitlines():
        if "|" not in line:
            continue
        path = line.split("|", 1)[0].strip()
        if path:
            changed_files.append(path)
    return changed_files


def _collection_error(incident: Incident, db_session: Session, error: Exception) -> Evidence:
    evidence = Evidence(
        incident_id=incident.id,
        category="collection_error",
        content={"collector": "git", "error": str(error)},
    )
    db_session.add(evidence)
    db_session.commit()
    db_session.refresh(evidence)
    return evidence


def collect_git_evidence(
    incident: Incident, db_session: Session, repo_path: str | Path = "."
) -> Evidence:
    """Persist factual Git activity around an incident without making causal claims."""
    start, end = determine_window(incident)
    # A short buffer helps include a commit created immediately before the incident.
    start = start - datetime.timedelta(minutes=1)
    repo = Path(repo_path).resolve()

    try:
        output = _run_git(
            [
                "git",
                "log",
                f"--since={_as_utc(start).isoformat()}",
                f"--until={_as_utc(end).isoformat()}",
                f"--pretty=format:{GIT_LOG_FORMAT}",
                "--",
                "simulator/",
            ],
            repo,
        )

        commits = []
        for line in output.splitlines():
            try:
                sha, timestamp, message = line.split("|", 2)
            except ValueError:
                continue

            commits.append(
                {
                    "sha": sha,
                    "timestamp": _parse_git_timestamp(timestamp).isoformat(),
                    "message": message,
                    "changed_files": _changed_files(sha, repo),
                    "config_diff": _run_git(
                        ["git", "show", sha, "--", "simulator/config.json"], repo
                    ),
                }
            )

        evidence = Evidence(
            incident_id=incident.id,
            category="observed_fact",
            content={
                "source": "git",
                "commits": commits,
                "query_window": {"start": start.isoformat(), "end": end.isoformat()},
            },
        )
        db_session.add(evidence)
        db_session.commit()
        db_session.refresh(evidence)
        return evidence
    except (OSError, subprocess.SubprocessError) as error:
        return _collection_error(incident, db_session, error)
