from typing import Optional
from app.monitoring.analyzer_base import BaseAnalyzer
from app.monitoring.analyzers.ci_analyzer import CIAnalyzer
from app.monitoring.analyzers.pull_request_analyzer import PullRequestAnalyzer
from app.monitoring.analyzers.issue_analyzer import IssueAnalyzer
from app.monitoring.analyzers.repository_activity_analyzer import RepositoryActivityAnalyzer
from app.monitoring.analyzers.dependency_analyzer import DependencyAnalyzer
from app.monitoring.analyzers.security_analyzer import SecurityAnalyzer

ANALYZER_REGISTRY: dict[str, BaseAnalyzer] = {}

def register_analyzer(analyzer: BaseAnalyzer) -> None:
    ANALYZER_REGISTRY[analyzer.key] = analyzer

def get_analyzer(key: str) -> Optional[BaseAnalyzer]:
    return ANALYZER_REGISTRY.get(key)

register_analyzer(CIAnalyzer())
register_analyzer(PullRequestAnalyzer())
register_analyzer(IssueAnalyzer())
register_analyzer(RepositoryActivityAnalyzer())
register_analyzer(DependencyAnalyzer())
register_analyzer(SecurityAnalyzer())
