import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from app.models.finding import Finding
from app.services.ai_analysis_service import AINotConfiguredError, AIAnalysisFailedError


@pytest.fixture
def test_finding(db_session, test_user_repository):
    finding = Finding(
        repository_id=test_user_repository.id,
        category="security",
        type="secret_leak",
        title="Hardcoded API Key",
        description="Key found in config.",
        severity="high",
        status="open",
        source="scanner",
        evidence={"line": 42},
        priority="P1",
        fingerprint="test1234_ai"
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)
    return finding


@pytest.fixture
def other_user_repository(db_session):
    from app.models.user import User
    from app.models.github_connection import GitHubConnection
    from app.models.repository import Repository
    
    other_user = User(email="other_ai@example.com", auth_provider="test")
    db_session.add(other_user)
    db_session.commit()
    
    conn = GitHubConnection(
        user_id=other_user.id, 
        installation_id=999, 
        account_login="other_ai", 
        account_type="User", 
        status="active"
    )
    db_session.add(conn)
    db_session.commit()
    
    repo = Repository(
        connection_id=conn.id, 
        github_repo_id=999, 
        full_name="other_ai/repo", 
        monitoring_enabled=True
    )
    db_session.add(repo)
    db_session.commit()
    
    return repo


@pytest.fixture
def other_user_finding(db_session, other_user_repository):
    finding = Finding(
        repository_id=other_user_repository.id,
        category="security",
        type="secret_leak",
        title="Other Hardcoded API Key",
        description="Key found in config.",
        severity="high",
        status="open",
        source="scanner",
        evidence={"line": 99},
        priority="P1",
        fingerprint="test999_ai"
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)
    return finding


@pytest.fixture
def mock_ai_analysis(test_finding):
    mock = MagicMock()
    mock.id = uuid.uuid4()
    mock.finding_id = test_finding.id
    mock.provider = "gemini"
    mock.model = "gemini-1.5-pro"
    mock.status = "completed"
    mock.requested_at = datetime.now(timezone.utc)
    mock.completed_at = datetime.now(timezone.utc)
    mock.summary = "Test summary"
    mock.severity_assessment = "High"
    mock.confidence = "High"
    mock.recommendations = "Fix it"
    mock.error_message = None # Explicitly ensuring not in schema
    return mock


@pytest.mark.asyncio
@patch("app.api.v1.findings.ai_analysis_service.request_finding_analysis")
async def test_trigger_analysis_success(mock_request, authorized_client, test_finding, mock_ai_analysis):
    mock_request.return_value = mock_ai_analysis
    
    response = await authorized_client.post(f"/api/v1/findings/{test_finding.id}/ai-analysis")
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(mock_ai_analysis.id)
    assert data["provider"] == "gemini"
    assert "error_message" not in data
    mock_request.assert_called_once()
    

@pytest.mark.asyncio
@patch("app.api.v1.findings.ai_analysis_service.request_finding_analysis")
async def test_trigger_analysis_not_configured(mock_request, authorized_client, test_finding):
    mock_request.side_effect = AINotConfiguredError()
    
    response = await authorized_client.post(f"/api/v1/findings/{test_finding.id}/ai-analysis")
    
    assert response.status_code == 400
    assert "No valid AI connection" in response.json()["detail"]


@pytest.mark.asyncio
@patch("app.api.v1.findings.ai_analysis_service.request_finding_analysis")
async def test_trigger_analysis_failed_provider(mock_request, authorized_client, test_finding):
    mock_request.side_effect = AIAnalysisFailedError(
        code="ai_provider_rate_limited",
        message="The AI provider is rate limited.",
        status_code=429
    )
    
    response = await authorized_client.post(f"/api/v1/findings/{test_finding.id}/ai-analysis")
    
    assert response.status_code == 429
    assert response.json()["detail"] == "The AI provider is rate limited."


@pytest.mark.asyncio
async def test_trigger_analysis_unowned_finding(authorized_client, other_user_finding):
    response = await authorized_client.post(f"/api/v1/findings/{other_user_finding.id}/ai-analysis")
    
    assert response.status_code == 404


@pytest.mark.asyncio
@patch("app.api.v1.findings.ai_analysis_service.get_latest_analysis")
async def test_get_latest_analysis_none(mock_get, authorized_client, test_finding):
    mock_get.return_value = None
    
    response = await authorized_client.get(f"/api/v1/findings/{test_finding.id}/ai-analysis")
    
    assert response.status_code == 200
    data = response.json()
    assert data["exists"] is False
    assert "id" not in data


@pytest.mark.asyncio
@patch("app.api.v1.findings.ai_analysis_service.get_latest_analysis")
async def test_get_latest_analysis_success(mock_get, authorized_client, test_finding, mock_ai_analysis):
    mock_get.return_value = mock_ai_analysis
    
    response = await authorized_client.get(f"/api/v1/findings/{test_finding.id}/ai-analysis")
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(mock_ai_analysis.id)
    assert "exists" not in data


@pytest.mark.asyncio
async def test_get_latest_analysis_unowned_finding(authorized_client, other_user_finding):
    response = await authorized_client.get(f"/api/v1/findings/{other_user_finding.id}/ai-analysis")
    
    assert response.status_code == 404


@pytest.mark.asyncio
@patch("app.api.v1.findings.ai_analysis_service.list_analyses")
async def test_list_analyses_history(mock_list, authorized_client, test_finding, mock_ai_analysis):
    mock_list.return_value = (1, [mock_ai_analysis])
    
    response = await authorized_client.get(f"/api/v1/findings/{test_finding.id}/ai-analysis/history")
    
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == str(mock_ai_analysis.id)
    assert data["limit"] == 50
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_list_analyses_unowned_finding(authorized_client, other_user_finding):
    response = await authorized_client.get(f"/api/v1/findings/{other_user_finding.id}/ai-analysis/history")
    
    assert response.status_code == 404
