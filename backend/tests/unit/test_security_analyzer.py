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
    assert finding1.fingerprint == "security:123:dependabot:1"

    finding2 = findings[1]
    assert finding2.severity == "medium"
    assert "flask" in finding2.title
    assert finding2.evidence["package_name"] == "flask"
    assert finding2.fingerprint == "security:123:dependabot:3"

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


@pytest.mark.asyncio
@patch("app.monitoring.monitor_service.GitHubAppClient")
async def test_run_analyzer_verifies_sync_path_for_security(mock_client_class):
    db_session = MagicMock()
    test_user_repository = MagicMock()
    test_user_repository.monitoring_enabled = True
    test_user_repository.connection = MagicMock()
    test_user_repository.connection.installation_id = 999
    
    mock_client_instance = AsyncMock()
    mock_client_instance.__aenter__.return_value = mock_client_instance
    mock_client_class.return_value = mock_client_instance
    mock_client_instance.list_dependabot_alerts.return_value = []
    

    result = await run_analyzer(db_session, "security", test_user_repository)
    
    assert result.status == "success"
    assert result.sync_result is not None

@pytest.mark.asyncio
async def test_security_analyzer_repository_scope(security_analyzer):
    """Confirm the analyzer can be invoked given only a repository and client, independent of any event."""
    context = MagicMock(spec=AnalyzerContext)
    context.repository = MagicMock()
    context.repository.full_name = "test/repo2"
    context.repository.id = 999
    context.client = AsyncMock()
    context.normalized_event = None
    
    context.client.list_dependabot_alerts.return_value = [
        {
            "number": 10,
            "state": "open",
            "security_advisory": {
                "summary": "High Risk",
                "severity": "high"
            },
            "dependency": {
                "package": {"name": "lodash"}
            }
        }
    ]
    
    findings = await security_analyzer.analyze(context)
    
    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "high"
    assert finding.evidence["package_name"] == "lodash"
    assert finding.type_ == "dependabot_alert_open"
