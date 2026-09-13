import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.monitoring.analyzers.security_analyzer import SecurityAnalyzer
from app.monitoring.analyzer_base import AnalyzerContext, FindingDraft
from app.integrations.github.exceptions import GitHubAuthError
from app.monitoring.monitor_service import run_analyzer

@pytest.fixture
def security_analyzer():
    return SecurityAnalyzer()

@pytest.fixture
def mock_context():
    context = MagicMock(spec=AnalyzerContext)
    context.repository = MagicMock()
    context.repository.full_name = "test/repo"
    context.repository.id = 123
    context.client = AsyncMock()
    return context

@pytest.mark.asyncio
async def test_analyzer_returns_open_alerts(security_analyzer, mock_context):
    mock_context.client.list_dependabot_alerts.return_value = [
        {
            "number": 1,
            "state": "open",
            "security_advisory": {
                "summary": "Critical RCE",
                "severity": "critical"
            },
            "dependency": {
                "package": {"name": "django"}
            }
        },
        {
            "number": 2,
            "state": "dismissed",
            "security_advisory": {
                "summary": "Low Severity Issue",
                "severity": "low"
            },
            "dependency": {
                "package": {"name": "requests"}
            }
        },
        {
            "number": 3,
            "state": "open",
            "security_advisory": {
                "summary": "Medium SQL Injection",
                "severity": "medium"
            },
            "dependency": {
                "package": {"name": "flask"}
            }
        }
    ]

    findings = await security_analyzer.analyze(mock_context)
    
    assert len(findings) == 2
    
    finding1 = findings[0]
    assert finding1.type_ == "dependabot_alert_open"
    assert finding1.severity == "critical"
    assert "django" in finding1.title
    assert "Critical RCE" in finding1.description
    assert finding1.evidence == {
        "github_alert_number": 1,
        "package_name": "django",
        "severity": "critical"
    }

    finding2 = findings[1]
    assert finding2.severity == "medium"
    assert "flask" in finding2.title
    assert finding2.evidence["package_name"] == "flask"

@pytest.mark.asyncio
async def test_analyzer_no_alerts(security_analyzer, mock_context):
    mock_context.client.list_dependabot_alerts.return_value = []

    findings = await security_analyzer.analyze(mock_context)
    assert len(findings) == 0

@pytest.mark.asyncio
async def test_analyzer_github_auth_error(security_analyzer, mock_context):
    mock_context.client.list_dependabot_alerts.side_effect = GitHubAuthError("403 Forbidden")

    findings = await security_analyzer.analyze(mock_context)
    assert len(findings) == 0

@pytest.mark.asyncio
async def test_analyzer_missing_fields_graceful(security_analyzer, mock_context):
    mock_context.client.list_dependabot_alerts.return_value = [
         {
             "number": 99,
             "state": "open"
             # Missing security_advisory and dependency
         }
    ]
    findings = await security_analyzer.analyze(mock_context)
    assert len(findings) == 1
    
    finding = findings[0]
    assert finding.severity == "low"
    assert "unknown" in finding.title
    assert finding.evidence["package_name"] == "unknown"
