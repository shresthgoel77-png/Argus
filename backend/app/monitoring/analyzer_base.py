from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from app.models.repository import Repository
from app.integrations.github.client import GitHubAppClient
from app.integrations.github.webhook_events import NormalizedWebhookEvent

@dataclass
class AnalyzerContext:
    repository: Repository
    normalized_event: Optional[NormalizedWebhookEvent] = None
    client: Optional[GitHubAppClient] = None

@dataclass
class FindingDraft:
    category: str
    type_: str
    title: str
    description: str
    severity: str
    evidence: dict[str, Any]

class BaseAnalyzer(ABC):
    key: str
    category: str
    requires_client: bool = False

    @abstractmethod
    def analyze(self, context: AnalyzerContext) -> list[FindingDraft]:
        pass
