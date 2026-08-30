"""
RCA engine — orchestrates the full AI-driven root cause analysis:
fetch incident, build evidence, call AI, validate, retry once on
validation failure, persist results.

SECURITY NOTE (defense in depth):
    recommended_remediation.action_type is the ONLY piece of the AI's
    output that will ever be used to trigger an action in Phase 7.
    Even then, Phase 7 MUST re-validate against ALLOWED_REMEDIATION_TYPES
    before executing anything.  This phase's allowlist check does NOT
    exempt Phase 7 from checking again.

    NEVER execute, eval, or shell out based on any AI-returned field.
"""

import logging

from sqlalchemy.orm import Session

from app.models import Evidence, Incident
from app.ai.client import AICallError, AIResponseParseError, call_rca_model
from app.ai.evidence_package import build_evidence_package
from app.ai.prompt_builder import build_rca_retry_prompt
from app.ai.validator import RCAValidationError, validate_rca_output

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors mapped to HTTP status codes at the API layer
# ---------------------------------------------------------------------------

class IncidentNotFoundError(Exception):
    """Incident does not exist (-> 404)."""
    pass


class RCAStateError(Exception):
    """Incident is not in the right state for RCA (-> 409)."""
    pass


class AIServiceError(Exception):
    """AI call or validation failed after retry (-> 502)."""
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _persist_error(
    db_session: Session,
    incident_id: int,
    error_detail: str,
    raw_response: object = None,
) -> Evidence:
    """Persist an ai_rca_error evidence row."""
    content = {"error": error_detail}
    if raw_response is not None:
        content["raw_response"] = raw_response
    row = Evidence(
        incident_id=incident_id,
        category="ai_rca_error",
        content=content,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _persist_success(
    db_session: Session,
    incident: Incident,
    validated_output: dict,
) -> Evidence:
    """Persist an ai_rca evidence row and advance incident status."""
    row = Evidence(
        incident_id=incident.id,
        category="ai_rca",
        content=validated_output,
    )
    db_session.add(row)
    incident.status = "rca_complete"
    db_session.commit()
    db_session.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def run_rca(incident_id: int, db_session: Session) -> dict:
    """
    Run a full AI-driven root cause analysis for the given incident.

    Returns {"incident_id", "rca", "evidence_id"} on success.
    Raises IncidentNotFoundError / RCAStateError / AIServiceError.
    """

    # 1. Fetch incident
    incident = db_session.query(Incident).filter(Incident.id == incident_id).first()
    if incident is None:
        raise IncidentNotFoundError(f"Incident {incident_id} not found")

    # 2. Status guard — must be "investigated"
    if incident.status != "investigated":
        raise RCAStateError(
            f"Incident {incident_id} has status '{incident.status}'; "
            f"must be 'investigated' before running RCA"
        )

    # 3. Idempotency guard — no existing ai_rca evidence
    existing_rca = (
        db_session.query(Evidence)
        .filter(Evidence.incident_id == incident_id, Evidence.category == "ai_rca")
        .first()
    )
    if existing_rca is not None:
        raise RCAStateError(
            f"RCA has already been run for incident {incident_id}"
        )

    # 4. Build evidence package
    evidence_package = build_evidence_package(incident, db_session)

    # 5. Call AI model
    try:
        raw_response = call_rca_model(evidence_package)
    except (AICallError, AIResponseParseError) as exc:
        _persist_error(db_session, incident_id, str(exc))
        raise AIServiceError(f"AI call failed: {exc}") from exc

    # 6. Validate — with one bounded retry on validation failure
    try:
        validated = validate_rca_output(raw_response, evidence_package)
    except RCAValidationError as first_error:
        logger.warning(
            "RCA validation failed for incident %s (attempt 1): %s",
            incident_id, first_error,
        )
        _persist_error(
            db_session, incident_id,
            f"Validation attempt 1: {first_error}",
            raw_response=raw_response,
        )

        # Retry ONCE with a stricter prompt including the exact error
        retry_prompt = build_rca_retry_prompt(
            evidence_package, str(first_error), raw_response,
        )
        try:
            raw_response_2 = call_rca_model.__wrapped__(evidence_package, retry_prompt) \
                if hasattr(call_rca_model, '__wrapped__') \
                else _call_retry(evidence_package, retry_prompt)
        except (AICallError, AIResponseParseError) as exc:
            _persist_error(db_session, incident_id, f"Retry AI call failed: {exc}")
            raise AIServiceError(f"AI retry call failed: {exc}") from exc

        try:
            validated = validate_rca_output(raw_response_2, evidence_package)
        except RCAValidationError as second_error:
            logger.warning(
                "RCA validation failed for incident %s (attempt 2): %s",
                incident_id, second_error,
            )
            _persist_error(
                db_session, incident_id,
                f"Validation attempt 2 (final): {second_error}",
                raw_response=raw_response_2,
            )
            raise AIServiceError(
                f"RCA validation failed after retry: {second_error}"
            ) from second_error

    # 7. Success — persist validated RCA
    rca_dict = validated.model_dump()
    evidence_row = _persist_success(db_session, incident, rca_dict)

    # 8. Return result
    return {
        "incident_id": incident.id,
        "rca": rca_dict,
        "evidence_id": evidence_row.id,
    }


def _call_retry(evidence_package: dict, retry_prompt: str) -> dict:
    """Call the AI model with a retry prompt for validation correction."""
    import os
    import json
    from google import genai
    from google.genai import types
    from app.ai.prompt_builder import build_system_prompt
    from app.ai.client import AICallError, AIResponseParseError, _clean_json_response

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise AICallError("GEMINI_API_KEY environment variable is missing or empty.")

    client = genai.Client(api_key=api_key)
    model = os.getenv("AI_MODEL", "gemini-2.5-flash")
    system_prompt = build_system_prompt()

    try:
        response = client.models.generate_content(
            model=model,
            contents=retry_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                temperature=0.1  # Lower temp for stricter adherence
            )
        )
    except Exception as e:
        raise AICallError(f"Failed to call Gemini API (retry): {str(e)}") from e

    if not response.text:
        raise AIResponseParseError("Empty response from Gemini API (retry)")

    raw_text = response.text
    cleaned_json = _clean_json_response(raw_text)

    try:
        return json.loads(cleaned_json)
    except json.JSONDecodeError as e:
        raise AIResponseParseError(
            f"Failed to parse JSON response (retry): {str(e)}\nRaw: {raw_text}"
        ) from e
