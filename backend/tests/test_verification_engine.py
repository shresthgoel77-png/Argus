import datetime

import pytest

from app.db import Base, SessionLocal, engine
from app.models import Incident, VerificationResult
from app.verification.engine import (
    VerificationStateError,
    run_verification,
)


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    session.query(VerificationResult).delete()
    session.query(Incident).delete()
    session.commit()
    yield session
    session.rollback()
    session.close()


def make_incident(db_session, status="remediated", incident_type="high_error_rate"):
    incident = Incident(
        type=incident_type,
        service="simulator",
        severity="high",
        timestamp=datetime.datetime.utcnow(),
        trigger="test",
        status=status,
        initial_metrics={"value": 12.5, "firing": True},
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)
    return incident


def test_verification_recovers_and_persists_result(monkeypatch, db_session):
    incident = make_incident(db_session)
    detector_results = iter(
        [
            {"firing": False, "value": 0.0, "severity": None},
            {"firing": False, "value": 0.2, "severity": None},
        ]
    )
    monkeypatch.setattr(
        "app.verification.engine.DETECTOR_BY_INCIDENT_TYPE",
        {"high_error_rate": lambda service: next(detector_results)},
    )
    monkeypatch.setattr("app.verification.engine._check_simulator_health", lambda: "healthy")
    monkeypatch.setenv("VERIFICATION_MAX_WAIT_SECONDS", "1")
    monkeypatch.setenv("VERIFICATION_POLL_INTERVAL_SECONDS", "0")

    result = run_verification(incident.id, db_session)

    assert result["recovered"] is True
    assert result["before_metrics"]["value"] == 12.5
    assert result["after_metrics"]["final_detector_result"]["value"] == 0.2
    assert len(result["after_metrics"]["poll_history"]) == 2
    db_session.refresh(incident)
    assert incident.status == "resolved"
    assert db_session.query(VerificationResult).count() == 1


def test_verification_times_out_without_recovery(monkeypatch, db_session):
    incident = make_incident(db_session)
    monkeypatch.setattr(
        "app.verification.engine.DETECTOR_BY_INCIDENT_TYPE",
        {"high_error_rate": lambda service: {"firing": True, "value": 12.5}},
    )
    monkeypatch.setattr("app.verification.engine._check_simulator_health", lambda: "healthy")
    monkeypatch.setenv("VERIFICATION_MAX_WAIT_SECONDS", "0")
    monkeypatch.setenv("VERIFICATION_POLL_INTERVAL_SECONDS", "0")

    result = run_verification(incident.id, db_session)

    assert result["recovered"] is False
    assert result["after_metrics"]["final_detector_result"]["firing"] is True
    db_session.refresh(incident)
    assert incident.status == "remediation_failed"


def test_verification_requires_remediated_incident(db_session):
    incident = make_incident(db_session, status="remediating")

    with pytest.raises(VerificationStateError, match="must be remediated"):
        run_verification(incident.id, db_session)


def test_verification_is_one_shot(monkeypatch, db_session):
    incident = make_incident(db_session)
    db_session.add(
        VerificationResult(
            incident_id=incident.id,
            before_metrics={},
            after_metrics={},
            recovered=True,
        )
    )
    db_session.commit()

    with pytest.raises(VerificationStateError, match="already been performed"):
        run_verification(incident.id, db_session)


def test_transient_prometheus_failure_is_recorded_and_polling_continues(
    monkeypatch, db_session
):
    incident = make_incident(db_session)
    from app.observability.prometheus_client import PrometheusUnavailableError

    detector_results = iter(
        [
            PrometheusUnavailableError("Prometheus down"),
            {"firing": False, "value": 0.2, "severity": None},
        ]
    )

    def detector(service):
        result = next(detector_results)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(
        "app.verification.engine.DETECTOR_BY_INCIDENT_TYPE",
        {"high_error_rate": detector},
    )
    monkeypatch.setattr("app.verification.engine._check_simulator_health", lambda: "healthy")
    monkeypatch.setenv("VERIFICATION_MAX_WAIT_SECONDS", "1")
    monkeypatch.setenv("VERIFICATION_POLL_INTERVAL_SECONDS", "0")

    result = run_verification(incident.id, db_session)

    assert result["recovered"] is True
    assert result["after_metrics"]["poll_history"][0]["detector_result"]["error"] == "Prometheus down"
