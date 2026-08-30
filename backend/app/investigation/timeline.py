import datetime

from app.models import Evidence, Incident


def _as_utc(value: datetime.datetime) -> datetime.datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc)


def _from_epoch(value: str | int | float, nanoseconds: bool = False) -> datetime.datetime:
    numeric = float(value)
    if nanoseconds:
        numeric /= 1_000_000_000
    return datetime.datetime.fromtimestamp(numeric, tz=datetime.timezone.utc)


def _entry(
    timestamp: datetime.datetime,
    event_type: str,
    description: str,
    evidence_id: int | None,
) -> tuple[datetime.datetime, dict]:
    timestamp = _as_utc(timestamp)
    return timestamp, {
        "timestamp": timestamp.isoformat(),
        "event_type": event_type,
        "description": description,
        "evidence_id": evidence_id,
    }


def build_timeline(incident: Incident, evidence_rows: list[Evidence]) -> list[dict]:
    """Purely transform persisted evidence into a chronological investigation timeline."""
    entries = [
        _entry(
            incident.timestamp,
            "incident_detected",
            f"Incident {incident.id} was detected ({incident.type}).",
            None,
        )
    ]

    for evidence in evidence_rows:
        content = evidence.content or {}
        for commit in content.get("commits", []):
            try:
                timestamp = datetime.datetime.fromisoformat(commit["timestamp"])
            except (KeyError, TypeError, ValueError):
                continue
            entries.append(
                _entry(
                    timestamp,
                    "git_commit",
                    f"Commit {commit.get('sha', '')[:7]}: {commit.get('message', '')}",
                    evidence.id,
                )
            )

        matched_lines = content.get("matched_lines", [])
        log_times = []
        for line in matched_lines:
            try:
                log_times.append(_from_epoch(line["timestamp"], nanoseconds=True))
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
        if log_times:
            entries.append(
                _entry(min(log_times), "log_first_match", "First matched log entry.", evidence.id)
            )
            entries.append(
                _entry(max(log_times), "log_last_match", "Last matched log entry.", evidence.id)
            )

        datapoints = content.get("datapoints", [])
        valid_points = []
        for point in datapoints:
            try:
                valid_points.append((_from_epoch(point[0]), float(point[1])))
            except (IndexError, TypeError, ValueError, OverflowError):
                continue
        if valid_points:
            peak_time, peak_value = max(valid_points, key=lambda point: point[1])
            signal = content.get("signal", "metric")
            entries.append(
                _entry(
                    peak_time,
                    "metric_peak",
                    f"{signal} peak observed at {peak_value}.",
                    evidence.id,
                )
            )

    return [entry for _, entry in sorted(entries, key=lambda item: item[0])]
