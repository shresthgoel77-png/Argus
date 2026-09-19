import uuid
import pytest
from unittest.mock import MagicMock, patch

from app.models.repository import Repository
from app.models.finding import Finding
from app.models.repository_health_snapshot import RepositoryHealthSnapshot
from app.services.needs_attention_service import NeedsAttentionDTO
from app.services.repository_summary_context_builder import (
    build_repository_summary_context,
    REPO_SUMMARY_SYSTEM_INSTRUCTIONS_BLOCK
)
from app.services.ai_context_common import wrap_untrusted_content


@pytest.fixture
def mock_db_session():
    return MagicMock()


@pytest.fixture
def mock_repository():
    repo = MagicMock(spec=Repository)
    repo.id = uuid.uuid4()
    repo.full_name = "test/test-repo"
    repo.monitoring_enabled = True
    return repo


@patch("app.services.repository_summary_context_builder.get_needs_attention")
def test_build_repository_summary_context_with_findings_and_snapshot(
    mock_get_needs_attention, mock_db_session, mock_repository
):
    repo_id = mock_repository.id

    # Mock DB Repository lookup
    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = mock_repository
    mock_db_session.query.return_value = mock_query

    # Mock findings and snapshot
    finding1 = MagicMock(spec=Finding)
    finding1.severity = "critical"
    finding1.category = "security"
    finding1.title = "Critical security issue"
    finding1.description = "Test description"
    finding1.evidence = {"severity": "critical"}

    snapshot = MagicMock(spec=RepositoryHealthSnapshot)
    snapshot.overall_score = 42
    snapshot.category_scores = {"security": 10, "code_quality": 32}
    
    mock_get_needs_attention.return_value = NeedsAttentionDTO(
        findings=[finding1] * 12,  # Let's pretend it returns 12, but we only asked for 10
        health_snapshot=snapshot,
        reasons=["Reason 1", "Reason 2"]
    )

    context = build_repository_summary_context(mock_db_session, repo_id)

    assert context.repository_name == "test/test-repo"
    assert context.system_instructions == REPO_SUMMARY_SYSTEM_INSTRUCTIONS_BLOCK
    
    # Assert wrapper exists
    assert context.untrusted_content.startswith("<untrusted_repository_content>\n")
    assert context.untrusted_content.endswith("</untrusted_repository_content>")

    # Check inner content
    assert "Repository Name: test/test-repo" in context.untrusted_content
    assert "Monitoring Enabled: True" in context.untrusted_content
    assert "Overall Health Score: 42" in context.untrusted_content
    assert "Reason 1" in context.untrusted_content
    assert "Critical security issue" in context.untrusted_content


@patch("app.services.repository_summary_context_builder.get_needs_attention")
def test_build_repository_summary_context_no_findings_no_snapshot(
    mock_get_needs_attention, mock_db_session, mock_repository
):
    repo_id = mock_repository.id

    # Mock DB Repository lookup
    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = mock_repository
    mock_db_session.query.return_value = mock_query

    mock_get_needs_attention.return_value = NeedsAttentionDTO(
        findings=[],
        health_snapshot=None,
        reasons=[]
    )

    context = build_repository_summary_context(mock_db_session, repo_id)

    assert "Overall Health Score: N/A" in context.untrusted_content
    assert "Top Findings: None" in context.untrusted_content
    assert "Repository Name: test/test-repo" in context.untrusted_content

    assert context.untrusted_content.startswith("<untrusted_repository_content>\n")


def test_build_repository_summary_context_repo_not_found(mock_db_session):
    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = None
    mock_db_session.query.return_value = mock_query

    with pytest.raises(ValueError, match="Repository .* not found"):
        build_repository_summary_context(mock_db_session, uuid.uuid4())
