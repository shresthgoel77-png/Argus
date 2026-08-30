import json
from .schema import ALLOWED_REMEDIATION_TYPES, RCAOutput

def build_system_prompt() -> str:
    """
    Constructs the system prompt instructing the model on constraints and expected output schema.
    """
    schema_fields = list(RCAOutput.model_fields.keys())
    
    return f"""You are an expert strict AI Reliability Engineer investigating system incidents.
Your ONLY output must be a single JSON object matching the exact schema below.
DO NOT output any conversational text, prose, explanations before or after the JSON, and DO NOT wrap the JSON in markdown code blocks like ```json.

REQUIRED SCHEMA (Output ONLY a parseable JSON object matching this structure):
{{
    "summary": "string - brief summary of the incident",
    "impact": "string - user or system impact",
    "affected_components": ["string", "string"],
    "root_cause": "string - the confirmed or suspected root cause",
    "confidence": "string - strictly one of: 'low', 'medium', 'high'",
    "supporting_evidence": ["string", "string"], // exactly matching IDs from the provided evidence package
    "alternative_hypotheses": ["string", "string"],
    "recommended_fix": "string - explanation of the fix",
    "recommended_remediation": {{
        "action_type": "string - strictly one of: {ALLOWED_REMEDIATION_TYPES}",
        "params": {{}}, // parameters for the action
        "rationale": "string - why this action is recommended"
    }}
}}

STRICT INSTRUCTIONS:
1. NEVER invent metrics, logs, emits, or evidence that is not explicitly present in the supplied evidence package.
2. The `supporting_evidence` list must ONLY contain exact evidence IDs that appear in the supplied package.
3. Distinguish between facts (category="observed_fact") and hypotheses (category="hypothesis") from the provided evidence. DO NOT upgrade a hypothesis to a stated fact in the `root_cause`.
4. Only set `recommended_remediation.action_type` to literally one of these verbatim choices: {ALLOWED_REMEDIATION_TYPES}.
5. NEVER state or imply that any remediation action has already been executed — only RECOMMEND one.
6. If the provided evidence is insufficient to identify a plausible root cause, set confidence="low" and state honestly in `root_cause` that the root cause could not be determined, rather than fabricating certainty.
7. Return raw JSON text ONLY.
"""

def build_rca_prompt(evidence_package: dict) -> str:
    """
    Constructs the user message containing the evidence package.
    """
    return f"""Here is the evidence package for the incident:

{json.dumps(evidence_package, indent=2)}

Please analyze this evidence package and provide the RCAOutput strictly as JSON."""


def build_rca_retry_prompt(
    evidence_package: dict,
    validation_error: str,
    raw_response: object,
) -> str:
    """
    Constructs a retry prompt that includes the exact validation error
    from the first attempt, the model's offending response, and a
    reminder of the constraints it violated.
    """
    return f"""Your previous response failed validation with the following error:

ERROR: {validation_error}

Your previous (invalid) response was:
{json.dumps(raw_response, indent=2) if isinstance(raw_response, dict) else str(raw_response)}

Please correct your response. Key constraints:
1. `supporting_evidence` must ONLY contain exact evidence IDs from the evidence package below — do NOT invent IDs.
2. `recommended_remediation.action_type` must be exactly one of: {ALLOWED_REMEDIATION_TYPES}
3. `confidence` must be exactly one of: "low", "medium", "high"
4. All required fields must be present and match the schema.

Here is the original evidence package again:

{json.dumps(evidence_package, indent=2)}

Return ONLY the corrected JSON object, no prose or markdown."""
