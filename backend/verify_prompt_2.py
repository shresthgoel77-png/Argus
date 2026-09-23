import asyncio
import uuid
from unittest.mock import MagicMock, AsyncMock
from app.monitoring.analyzer_base import AnalyzerContext
from app.monitoring.analyzers.dependency_analyzer import DependencyAnalyzer
from app.monitoring.analyzers.security_analyzer import SecurityAnalyzer
from app.monitoring.analyzers.code_quality_analyzer import CodeQualityAnalyzer
from app.models.finding import Finding
from app.models.repository_health_snapshot import RepositoryHealthSnapshot
from app.services.health_service import recalculate_repository_health
from sqlalchemy.orm import Session

async def run_manual_smoke_test():
    repo_id = uuid.uuid4()
    context = MagicMock(spec=AnalyzerContext)
    context.repository = MagicMock()
    context.repository.full_name = "mock/repo"
    context.repository.id = repo_id
    context.repository.default_branch = "main"
    context.repository.connection.installation_id = 999
    context.client = AsyncMock()
    context.normalized_event = None
    
    print("=== MANUAL SMOKE TEST PROMPT 2 ===\n")
    
    # 1. Dependency Analyzer
    async def get_content(full_name, path):
        if path == "package.json": return {"name": "mock"}
        return None
    context.client.get_repository_content.side_effect = get_content
    da = DependencyAnalyzer()
    da_result = await da.analyze(context)
    print("DependencyAnalyzer Result:")
    for f in da_result: print(f" - {f.severity.upper()} {f.type_}: {f.description}")
    
    # 2. Security Analyzer
    context.client.list_dependabot_alerts.return_value = [{
        "number": 1, "state": "open", 
        "security_advisory": {"summary": "Critical CVE", "severity": "critical"},
        "dependency": {"package": {"name": "mock-pkg"}}
    }]
    sa = SecurityAnalyzer()
    sa_result = await sa.analyze(context)
    print("\nSecurityAnalyzer Result:")
    for f in sa_result: print(f" - {f.severity.upper()} {f.type_}: {f.description}")
    
    # 3. Code Quality Analyzer
    from unittest.mock import patch
    with patch("app.monitoring.analyzers.code_quality_analyzer.get_branch_protection") as mock_bp:
        mock_bp.return_value = None
        cqa = CodeQualityAnalyzer()
        cqa_result = await cqa.analyze(context)
        print("\nCodeQualityAnalyzer Result:")
        for f in cqa_result: print(f" - {f.severity.upper()} {f.type_}: {f.description}")

    # 4. Health Recalculation
    print("\nRecalculate Repository Health Result:")
    # Mock finding extraction for health
    db = MagicMock(spec=Session)
    finding = Finding(category="security", severity="critical", type="mock_cve")
    
    with patch("app.services.health_service.get_all_open_findings_for_repository", return_value=[finding]):
        with patch("app.services.health_service.get_latest_snapshot", return_value=None):
            snapshot = recalculate_repository_health(db, repo_id)
            print(f" - Overall Score: {snapshot.overall_score}")
            print(f" - Category Scores: {snapshot.category_scores}")
            print(f" - Reasons: {snapshot.reasons}")
            
if __name__ == "__main__":
    asyncio.run(run_manual_smoke_test())
