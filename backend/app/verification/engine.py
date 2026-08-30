import datetime
import logging
import os
import time

import requests
from sqlalchemy.orm import Session

from app.detection.detectors import (
    detect_high_error_rate,
    detect_high_latency,
    detect_webhook_failure,
)
from app.models import Incident, VerificationResult
from app.observability.prometheus_client import PrometheusUnavailableError

logger = logging.getLogger(__name__)

DETECTOR_BY_INCIDENT_TYPE = {
    "high_error_rate": detect_high_error_rate,
    "high_latency": detect_high_latency,
    "webhook_failure": detect_webhook_failure,
}


class VerificationStateError(ValueError):
    """Raised when an incident cannot be verified in its current state."""


def _verification_setting(name: str, default: str, cast):
    try:
        return cast(os.getenv(name, default))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a valid {cast.__name__}") from error


def _check_simulator_health() -> str:
    simulator_url = os.getenv("SIMULATOR_URL", "http://localhost:9000").rstrip("/")
    try:
        response = requests.get(f"{simulator_url}/health", timeout=2.0)
        return "healthy" if response.status_code == 200 else "unreachable"
    except requests.RequestException:
        return "unreachable"


def run_verification(incident_id: int, db_session: Session) -> dict:
    incident = db_session.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise VerificationStateError(f"Incident {incident_id} not found")

    if incident.status != "remediated":
        raise VerificationStateError(
            f"Incident {incident_id} must be remediated before verification"
        )

    existing_result = (
        db_session.query(VerificationResult)
        .filter(VerificationResult.incident_id == incident_id)
        .first()
    )
    if existing_result:
        raise VerificationStateError(
            f"Verification has already been performed for incident {incident_id}"
        )

    detector = DETECTOR_BY_INCIDENT_TYPE.get(incident.type)
    if detector is None:
        raise VerificationStateError(
            f"No verification detector configured for incident type '{incident.type}'"
        )

    max_wait = _verification_setting("VERIFICATION_MAX_WAIT_SECONDS", "60", float)
    poll_interval = _verification_setting(
        "VERIFICATION_POLL_INTERVAL_SECONDS", "10", float
    )
    if max_wait < 0 or poll_interval < 0:
        raise ValueError("Verification wait and poll interval must not be negative")

    before_metrics = incident.initial_metrics
    poll_history = []
    started_at = time.monotonic()
    deadline = started_at + max_wait
    recovered = False
    last_detector_result = None
    last_health_status = "unreachable"
    zero_value_seen = False

    while True:
        checked_at = datetime.datetime.now(datetime.UTC)
        try:
            detector_result = detector(incident.service)
        except PrometheusUnavailableError as error:
            logger.warning(
                "Prometheus unavailable during verification for incident %s: %s",
                incident_id,
                error,
            )
            detector_result = {
                "firing": True,
                "error": str(error),
            }

        health_status = _check_simulator_health()
        poll_history.append(
            {
                "checked_at": checked_at.isoformat(),
                "detector_result": detector_result,
                "health_status": health_status,
            }
        )
        last_detector_result = detector_result
        last_health_status = health_status

        if not detector_result.get("firing", True) and health_status == "healthy":
            # A first zero can mean that no traffic has reached rate() yet; confirm it
            # on a later poll so an empty window is not mistaken for recovery.
            value = detector_result.get("value")
            if value != 0.0 or zero_value_seen:
                recovered = True
                break
            zero_value_seen = True

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(poll_interval, remaining))

    after_metrics = {
        "final_detector_result": last_detector_result,
        "final_health_status": last_health_status,
        "poll_history": poll_history,
    }
    checked_at = datetime.datetime.now(datetime.UTC)
    verification = VerificationResult(
        incident_id=incident_id,
        before_metrics=before_metrics,
        after_metrics=after_metrics,
        recovered=recovered,
        checked_at=checked_at,
    )
    db_session.add(verification)
    incident.status = "resolved" if recovered else "remediation_failed"
    db_session.commit()
    db_session.refresh(verification)

    return {
        "verification_id": verification.id,
        "incident_id": incident_id,
        "recovered": recovered,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "checked_at": checked_at,
    }
