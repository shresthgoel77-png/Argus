from typing import Optional
from app.monitoring.analyzer_base import BaseAnalyzer

ANALYZER_REGISTRY: dict[str, BaseAnalyzer] = {}

def register_analyzer(analyzer: BaseAnalyzer) -> None:
    ANALYZER_REGISTRY[analyzer.key] = analyzer

def get_analyzer(key: str) -> Optional[BaseAnalyzer]:
    return ANALYZER_REGISTRY.get(key)
