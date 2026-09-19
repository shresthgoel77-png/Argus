import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from app.services.ai_analysis_service import AINotConfiguredError, AIAnalysisFailedError


@pytest.fixture
def other_user_repository(db_session):
    from app.models.user import User
    from app.models.github_connection import GitHubConnection
    from app.models.repository import Repository
    
    other_user = User(email="other_ai_repo@example.com", auth_provider="test")
    db_session.add(other_user)
    db_session.commit()
    
    conn = GitHubConnection(
        user_id=other_user.id, 
        installation_id=999, 
        account_login="other_ai_repo", 
        account_type="User", 
        status="active"
    )
    db_session.add(conn)
    db_session.commit()
    
    repo = Repository(
        connection_id=conn.id, 
        github_repo_id=999, 
        full_name="other_ai/repo2", 
        monitoring_enabled=True
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    return repo


@pytest.fixture
def mock_repo_ai_analysis(test_user_repository):
    mock = MagicMock()
    mock.id = uuid.uuid4()
    mock.repository_id = test_user_repository.id
    mock.finding_id = None
    mock.analysis_type = "repository_summary"
    mock.provider = "gemini"
    mock.model = "gemini-1.5-pro"
    mock.status = "completed"
    mock.requested_at = datetime.now(timezone.utc)
    mock.completed_at = datetime.now(timezone.utc)
    mock.summary = "Test summary"
    mock.confidence = "High"
    mock.recommendations = "Fix it"
    mock.error_message = None
    mock.severity_assessment = None
    return mock


@pytest.mark.asyncio
@patch("app.api.v1.repositories.request_repository_summary")
async def test_trigger_repo_analysis_success(mock_request, authorized_client, test_user_repository, mock_repo_ai_analysis):
    mock_request.return_value = mock_repo_ai_analysis
    
    response = await authorized_client.post(f"/api/v1/repositories/{test_user_repository.id}/ai-summary")
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(mock_repo_ai_analysis.id)
    assert data["provider"] == "gemini"
    mock_request.assert_called_once()


@pytest.mark.asyncio
@patch("app.api.v1.repositories.request_repository_summary")
async def test_trigger_repo_analysis_not_configured(mock_request, authorized_client, test_user_repository):
    mock_request.side_effect = AINotConfiguredError()
    
    response = await authorized_client.post(f"/api/v1/repositories/{test_user_repository.id}/ai-summary")
    
    assert response.status_code == 400


@pytest.mark.asyncio
@patch("app.api.v1.repositories.request_repository_summary")
async def test_trigger_repo_analysis_failed_provider(mock_request, authorized_client, test_user_repository):
    mock_request.side_effect = AIAnalysisFailedError(
        code="ai_provider_rate_limited",
        message="The AI provider is rate limited.",
        status_code=429
    )
    
    response = await authorized_client.post(f"/api/v1/repositories/{test_user_repository.id}/ai-summary")
    
    assert response.status_code == 429


@pytest.mark.asyncio
async def test_trigger_repo_analysis_unowned(authorized_client, other_user_repository):
    response = await authorized_client.post(f"/api/v1/repositories/{other_user_repository.id}/ai-summary")
    assert response.status_code == 404


@pytest.mark.asyncio
@patch("app.api.v1.repositories.get_latest_repo_analysis")
async def test_get_latest_repo_analysis_success(mock_get, authorized_client, test_user_repository, mock_repo_ai_analysis):
    mock_get.return_value = mock_repo_ai_analysis
    response = await authorized_client.get(f"/api/v1/repositories/{test_user_repository.id}/ai-summary")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(mock_repo_ai_analysis.id)
    assert data["summary"] == "Test summary"


@pytest.mark.asyncio
@patch("app.api.v1.repositories.get_latest_repo_analysis")
async def test_get_latest_repo_analysis_none(mock_get, authorized_client, test_user_repository):
    mock_get.return_value = None
    response = await authorized_client.get(f"/api/v1/repositories/{test_user_repository.id}/ai-summary")
    assert response.status_code == 200
    data = response.json()
    assert data["exists"] is False


@pytest.mark.asyncio
async def test_get_latest_repo_analysis_unowned(authorized_client, other_user_repository):
    response = await authorized_client.get(f"/api/v1/repositories/{other_user_repository.id}/ai-summary")
    assert response.status_code == 404


@pytest.mark.asyncio
@patch("app.api.v1.repositories.list_repo_analyses")
async def test_history_repo_analysis_success(mock_list, authorized_client, test_user_repository, mock_repo_ai_analysis):
    mock_list.return_value = (1, [mock_repo_ai_analysis])
    response = await authorized_client.get(f"/api/v1/repositories/{test_user_repository.id}/ai-summary/history")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == str(mock_repo_ai_analysis.id)


@pytest.mark.asyncio
@patch("app.api.v1.repositories.list_repo_analyses")
async def test_history_repo_analysis_empty(mock_list, authorized_client, test_user_repository):
    mock_list.return_value = (0, [])
    response = await authorized_client.get(f"/api/v1/repositories/{test_user_repository.id}/ai-summary/history")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert len(data["items"]) == 0


@pytest.mark.asyncio
async def test_history_repo_analysis_unowned(authorized_client, other_user_repository):
    response = await authorized_client.get(f"/api/v1/repositories/{other_user_repository.id}/ai-summary/history")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_unauthenticated(async_client, test_user_repository):
    resp1 = await async_client.post(f"/api/v1/repositories/{test_user_repository.id}/ai-summary")
    assert resp1.status_code == 401
    
    resp2 = await async_client.get(f"/api/v1/repositories/{test_user_repository.id}/ai-summary")
    assert resp2.status_code == 401
    
    resp3 = await async_client.get(f"/api/v1/repositories/{test_user_repository.id}/ai-summary/history")
    assert resp3.status_code == 401
