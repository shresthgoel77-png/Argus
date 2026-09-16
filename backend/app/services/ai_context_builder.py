from dataclasses import dataclass
from typing import Any
from app.models.finding import Finding
from app.services.ai_context_common import (
    SYSTEM_INSTRUCTIONS_BLOCK,
    extract_untrusted_content,
    truncate,
    wrap_untrusted_content,
)

@dataclass
class FindingContext:
    category: str
    title: str
    system_instructions: str
    untrusted_content: str

_truncate = truncate

def _extract_untrusted_content(finding: Finding) -> str:
    return extract_untrusted_content(finding.category, finding.description, finding.evidence or {})

def build_context(finding: Finding) -> FindingContext:
    """
    Build a safe ai context containing trusted system info 
    and bounded untrusted repository content.
    """
    raw_untrusted = _extract_untrusted_content(finding)
    
    wrapped_untrusted = wrap_untrusted_content(raw_untrusted)

    return FindingContext(
        category=finding.category,
        title=finding.title,
        system_instructions=SYSTEM_INSTRUCTIONS_BLOCK,
        untrusted_content=wrapped_untrusted
    )
