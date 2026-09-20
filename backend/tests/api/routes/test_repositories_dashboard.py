import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch

from app.models.repository import Repository
from app.models.repository_health_snapshot import RepositoryHealthSnapshot
from app.models.finding import Finding
from app.models.ai_analysis import AIAnalysis

def test_get_dashboard_overview(
    client: TestClient,
    db_session: Session,
    mock_github_app,
    user_token_headers: dict[str, str],
    valid_repository: Repository,
):
    # 1. Setup mock data for health, findings (needs_attention + counts), activity feed is implicit, AI sum

    # Health
    snapshot = RepositoryHealthSnapshot(
        repository_id=valid_repository.id,
        computed_at=datetime.now(timezone.utc),
        overall_score=85,
        category_scores={"security": 90},
        reasons=["Good security score"]
    )
    db_session.add(snapshot)

    # Findings
    f1 = Finding(
        repository_id=valid_repository.id,
        category="security",
        type="vuln",
        title="High Vuln",
        description="desc",
        severity="high",
        priority="high",
        status="open",
        source="test",
        detected_at=datetime.now(timezone.utc),
    )
    f2 = Finding(
        repository_id=valid_repository.id,
        category="ci_cd",
        type="fail",
        title="CI fail",
        description="desc",
        severity="low",
        priority="low",
        status="open",
        source="test",
        detected_at=datetime.now(timezone.utc),
    )
    db_session.add_all([f1, f2])

    # AI
    ai = AIAnalysis(
        repository_id=valid_repository.id,
        analysis_type="repository_summary",
        status="completed",
        result_data={"summary": "test summary"},
        requested_at=datetime.now(timezone.utc)
    )
    db_session.add(ai)
    db_session.commit()

    # We mock Gemini / ai_analysis_service to ensure no call is made
    with patch("app.services.ai_analysis_service.get_gemini_client") as mock_gemini:
        response = client.get(
            f"/api/v1/repositories/{valid_repository.id}/dashboard",
            headers=user_token_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Struct check
        assert data["repository_id"] == str(valid_repository.id)
        
        assert data["health"]["overall_score"] == 85
        assert data["health"]["reasons"] == ["Good security score"]

        # Needs attention -> high severities
        # f1 is 'high', should be in needs attention findings
        na_findings = data["needs_attention"]["findings"]
        assert len(na_findings) == 1
        assert na_findings[0]["title"] == "High Vuln"
        assert data["needs_attention"]["reasons"] == ["Good security score"]

        assert data["ai_summary"]["status"] == "completed"
        assert data["ai_summary"]["result_data"] == {"summary": "test summary"}

        # Counts
        counts = data["finding_category_counts"]
        assert counts["security"] == 1
        assert counts["ci_cd"] == 1
        assert counts["dependencies"] == 0

        # No AI calls
        mock_gemini.assert_not_called()
