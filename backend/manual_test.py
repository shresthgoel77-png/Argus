import uuid
from unittest.mock import MagicMock

from app.models.repository import Repository
from app.models.finding import Finding
from app.models.repository_health_snapshot import RepositoryHealthSnapshot
from app.services.needs_attention_service import NeedsAttentionDTO
from app.services.repository_summary_context_builder import build_repository_summary_context

def main():
    mock_db_session = MagicMock()
    repo_id = uuid.uuid4()
    
    repo = MagicMock(spec=Repository)
    repo.id = repo_id
    repo.full_name = "test-org/test-repo-name"
    repo.monitoring_enabled = True
    
    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = repo
    mock_db_session.query.return_value = mock_query

    finding1 = MagicMock(spec=Finding)
    finding1.severity = "critical"
    finding1.priority = "high"
    finding1.category = "security"
    finding1.title = "Critical security issue in dependencies"
    finding1.description = "Found a vulnerability that could allow RCE."
    finding1.evidence = {"severity": "critical", "package_name": "serialize", "advisory_title": "RCE Vulnerability"}
    
    snapshot = MagicMock(spec=RepositoryHealthSnapshot)
    snapshot.overall_score = 42
    snapshot.category_scores = {"security": 10, "code_quality": 32}

    import app.services.repository_summary_context_builder as builder
    old_get_needs_attention = builder.get_needs_attention
    
    builder.get_needs_attention = MagicMock(return_value=NeedsAttentionDTO(
        findings=[finding1],
        health_snapshot=snapshot,
        reasons=["Reason 1: Outdated packages", "Reason 2: CI failure"]
    ))

    context = build_repository_summary_context(mock_db_session, repo_id)
    
    with open("manual_test_out.txt", "w", encoding="utf-8") as f:
        f.write("--- MANUAL INSPECTION OF GENERATED CONTEXT ---\n")
        f.write("\n[SYSTEM INSTRUCTIONS]\n")
        f.write(context.system_instructions)
        f.write("\n\n[UNTRUSTED CONTENT]\n")
        f.write(context.untrusted_content)
    
    builder.get_needs_attention = old_get_needs_attention

if __name__ == "__main__":
    main()
