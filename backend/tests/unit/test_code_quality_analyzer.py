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
    mock_get_branch_protection.assert_called_once_with(999, "test/repo", "main")

@pytest.mark.asyncio
@patch("app.monitoring.analyzers.code_quality_analyzer.get_branch_protection")
async def test_analyzer_github_auth_error(mock_get_branch_protection, code_quality_analyzer, mock_context):
    mock_get_branch_protection.side_effect = GitHubAuthError("403 Forbidden")

    findings = await code_quality_analyzer.analyze(mock_context)
    assert len(findings) == 0
    mock_get_branch_protection.assert_called_once_with(999, "test/repo", "main")
