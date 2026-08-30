"""
RCA output validator — validates AI responses against both the Pydantic
schema and the incident's actual evidence, rejecting hallucinated IDs
or invalid remediation types.
"""

from pydantic import ValidationError

from .schema import ALLOWED_REMEDIATION_TYPES, RCAOutput


class RCAValidationError(Exception):
    """Raised when the AI response fails schema or cross-check validation."""

    def __init__(self, message: str, details: object = None):
        super().__init__(message)
        self.details = details


def validate_rca_output(raw: dict, evidence_package: dict) -> RCAOutput:
    """
    Validate a raw AI response dict against the RCAOutput schema and
    cross-check it against the incident's real evidence.

    Returns a validated RCAOutput on success; raises RCAValidationError
    on any validation failure.
    """

    # 1. Parse against Pydantic schema
    try:
        rca = RCAOutput.model_validate(raw)
    except ValidationError as exc:
        raise RCAValidationError(
            f"Schema validation failed: {exc}",
            details=exc.errors(),
        ) from exc

    # 2. Cross-check: every supporting_evidence ID must exist in the
    #    evidence package. A hallucinated ID means the whole response is
    #    untrustworthy — do NOT silently drop and continue.
    valid_ids = {str(ev["id"]) for ev in evidence_package.get("evidence", [])}
    for eid in rca.supporting_evidence:
        if str(eid) not in valid_ids:
            raise RCAValidationError(f"hallucinated evidence id: {eid}")

    # 3. Cross-check: action_type must be an allowed remediation type.
    if rca.recommended_remediation.action_type not in ALLOWED_REMEDIATION_TYPES:
        raise RCAValidationError(
            f"Invalid remediation action_type: "
            f"'{rca.recommended_remediation.action_type}'. "
            f"Must be one of {ALLOWED_REMEDIATION_TYPES}"
        )

    # 4. confidence is already constrained by Literal["low","medium","high"]
    #    in the schema — pydantic rejects invalid values at step 1.

    return rca
