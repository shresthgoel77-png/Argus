import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.monitoring.analyzers.dependency_analyzer import DependencyAnalyzer
from app.monitoring.analyzer_base import AnalyzerContext, FindingDraft
from app.integrations.github.exceptions import GitHubAuthError
from app.monitoring.monitor_service import run_analyzer

@pytest.fixture
def dependency_analyzer():
    return DependencyAnalyzer()

@pytest.fixture
def mock_context():
    context = MagicMock(spec=AnalyzerContext)
    context.repository = MagicMock()
    context.repository.full_name = "test/repo"
    context.repository.id = 123
    context.client = AsyncMock()
    return context

@pytest.mark.asyncio
async def test_analyzer_manifest_present_no_lockfile(dependency_analyzer, mock_context):
    async def get_content(full_name, path):
        if path == "package.json":
            return {"name": "test"}
        return None  # No lockfiles exist

    mock_context.client.get_repository_content.side_effect = get_content

    findings = await dependency_analyzer.analyze(mock_context)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.type_ == "missing_lockfile"
    assert finding.severity == "medium"
    assert "package.json" in finding.description
    assert finding.evidence == {"manifest": "package.json"}

@pytest.mark.asyncio
async def test_analyzer_manifest_present_has_lockfile(dependency_analyzer, mock_context):
    async def get_content(full_name, path):
        if path == "package.json":
            return {"name": "test"}
        if path == "package-lock.json":
            return {"lockfileVersion": 2}
        return None

    mock_context.client.get_repository_content.side_effect = get_content

    findings = await dependency_analyzer.analyze(mock_context)
    assert len(findings) == 0

@pytest.mark.asyncio
async def test_analyzer_manifest_absent(dependency_analyzer, mock_context):
    async def get_content(full_name, path):
        # package.json not found
        return None

    mock_context.client.get_repository_content.side_effect = get_content

    findings = await dependency_analyzer.analyze(mock_context)
    assert len(findings) == 0

@pytest.mark.asyncio
async def test_analyzer_github_auth_error(dependency_analyzer, mock_context):
    mock_context.client.get_repository_content.side_effect = GitHubAuthError("403 Forbidden")

    findings = await dependency_analyzer.analyze(mock_context)
    assert len(findings) == 0

@pytest.mark.asyncio
@patch("app.monitoring.monitor_service.GitHubAppClient")
async def test_run_analyzer_constructs_client(mock_client_class):
    # Mocking db_session and repository to avoid fixture issues
    db_session = MagicMock()
    test_user_repository = MagicMock()
    test_user_repository.monitoring_enabled = True
    test_user_repository.connection = MagicMock()
    test_user_repository.connection.installation_id = 999
    db_session.commit = MagicMock()
    db_session.refresh = MagicMock()
    
    mock_client_instance = AsyncMock()
    # When used as async context manager, __aenter__ returns the instance
    mock_client_instance.__aenter__.return_value = mock_client_instance
    mock_client_class.return_value = mock_client_instance
    
    # We will mock the analyzer as well to avoid DB commit issues with real finding
    async def get_content(full_name, path):
        return None

    mock_client_instance.get_repository_content.side_effect = get_content
    
    # Run the real dependency analyzer through the service
    result = await run_analyzer(db_session, "dependency", test_user_repository)
    
    # Since requires_client=True, the mock Client should have been called
    assert result.status == "success", f"Failed with: {getattr(result, 'error_message', 'unknown')}"
    mock_client_class.assert_called_once_with(installation_id=test_user_repository.connection.installation_id)
