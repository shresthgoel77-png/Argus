import pytest
from unittest.mock import AsyncMock, MagicMock

from unittest.mock import AsyncMock, MagicMock, patch

from app.monitoring.analyzers.code_quality_analyzer import CodeQualityAnalyzer
from app.monitoring.analyzer_base import AnalyzerContext
from app.integrations.github.exceptions import GitHubAuthError

@pytest.fixture
def code_quality_analyzer():
    return CodeQualityAnalyzer()

@pytest.fixture
def mock_context():
    context = MagicMock(spec=AnalyzerContext)
    context.repository = MagicMock()
    context.repository.full_name = "test/repo"
    context.repository.id = 123
    context.repository.default_branch = "main"
    context.repository.connection.installation_id = 999
    context.client = AsyncMock()
    return context

@pytest.mark.asyncio
@patch("app.monitoring.analyzers.code_quality_analyzer.get_branch_protection")
async def test_analyzer_branch_protected(mock_get_branch_protection, code_quality_analyzer, mock_context):
    mock_get_branch_protection.return_value = {
        "url": "https://api.github.com/...",
        "required_status_checks": {}
    }

    findings = await code_quality_analyzer.analyze(mock_context)
    assert len(findings) == 0
    mock_get_branch_protection.assert_called_once_with(999, "test/repo", "main")

@pytest.mark.asyncio
@patch("app.monitoring.analyzers.code_quality_analyzer.get_branch_protection")
async def test_analyzer_branch_not_protected(mock_get_branch_protection, code_quality_analyzer, mock_context):
    mock_get_branch_protection.return_value = None

    findings = await code_quality_analyzer.analyze(mock_context)
    assert len(findings) == 1

    finding = findings[0]
    assert finding.type_ == "missing_branch_protection"
    assert finding.severity == "medium"
    assert finding.evidence == {"default_branch": "main"}
    assert "main" in finding.title
    assert finding.fingerprint == "code_quality:123:branch_protection:main"
    mock_get_branch_protection.assert_called_once_with(999, "test/repo", "main")

@pytest.mark.asyncio
@patch("app.monitoring.analyzers.code_quality_analyzer.get_branch_protection")
async def test_analyzer_github_auth_error(mock_get_branch_protection, code_quality_analyzer, mock_context):
    mock_get_branch_protection.side_effect = GitHubAuthError("403 Forbidden")

    findings = await code_quality_analyzer.analyze(mock_context)
    assert len(findings) == 0
    mock_get_branch_protection.assert_called_once_with(999, "test/repo", "main")

from app.monitoring.monitor_service import run_analyzer

@pytest.mark.asyncio
@patch("app.monitoring.monitor_service.GitHubAppClient")
@patch("app.monitoring.analyzers.code_quality_analyzer.get_branch_protection")
async def test_run_analyzer_verifies_sync_path_for_code_quality(mock_get_branch_protection, mock_client_class):
    db_session = MagicMock()
    test_user_repository = MagicMock()
    test_user_repository.monitoring_enabled = True
    test_user_repository.connection = MagicMock()
    test_user_repository.connection.installation_id = 999
    
    mock_client_instance = AsyncMock()
    mock_client_instance.__aenter__.return_value = mock_client_instance
    mock_client_class.return_value = mock_client_instance
    
    mock_get_branch_protection.return_value = None
    

    result = await run_analyzer(db_session, "code_quality", test_user_repository)
    
    assert result.status == "success"
    assert result.sync_result is not None

@pytest.mark.asyncio
@patch("app.monitoring.analyzers.code_quality_analyzer.get_branch_protection")
async def test_code_quality_analyzer_repository_scope(mock_get_branch_protection, code_quality_analyzer):
    """Confirm the analyzer can be invoked given only a repository and client, independent of any event."""
    context = MagicMock(spec=AnalyzerContext)
    context.repository = MagicMock()
    context.repository.full_name = "test/repo2"
    context.repository.default_branch = "dev"
    context.repository.id = 999
    context.repository.connection.installation_id = 1111
    context.client = AsyncMock()
    context.normalized_event = None
    
    mock_get_branch_protection.return_value = None

    findings = await code_quality_analyzer.analyze(context)
    
    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "medium"
    assert finding.type_ == "missing_branch_protection"
    assert finding.evidence["default_branch"] == "dev"
