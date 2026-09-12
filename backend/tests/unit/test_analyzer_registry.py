import pytest
from app.monitoring.analyzer_base import BaseAnalyzer, AnalyzerContext, FindingDraft
from app.monitoring.analyzers import ANALYZER_REGISTRY, register_analyzer, get_analyzer

class DummyAnalyzer(BaseAnalyzer):
    key = "dummy"
    category = "test"
    requires_client = False

    def analyze(self, context: AnalyzerContext) -> list[FindingDraft]:
        return []

def test_registry_is_empty_by_default():
    # Verify that the registry is empty initially
    assert len(ANALYZER_REGISTRY) == 0

def test_register_and_get_analyzer():
    analyzer = DummyAnalyzer()
    
    register_analyzer(analyzer)
    assert "dummy" in ANALYZER_REGISTRY
    assert get_analyzer("dummy") is analyzer
    
    # Clean up to keep tests isolated
    del ANALYZER_REGISTRY["dummy"]

def test_get_unknown_analyzer():
    # get_analyzer should return None for an unknown key
    assert get_analyzer("unknown_key") is None
