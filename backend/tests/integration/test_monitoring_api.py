import pytest
from httpx import AsyncClient
import uuid
from unittest.mock import patch, AsyncMock
import app.monitoring.analyzers as analyzers_registry
from app.monitoring.analyzer_base import BaseAnalyzer, AnalyzerContext, FindingDraft
from app.models.repository import Repository

class DummyAPIAnalyzer(BaseAnalyzer):
    key = "api_dummy"
    category = "test"
    requires_client = False
    
    def analyze(self, context: AnalyzerContext) -> list[FindingDraft]:
        return [
            FindingDraft(
                category="test",
                type_="test_finding",
                title="Test finding via API",
                description="Test description",
                severity="low",
                evidence={}
            )
        ]

@pytest.fixture(autouse=True)
def register_api_dummy_analyzer():
    analyzers_registry.ANALYZER_REGISTRY["api_dummy"] = DummyAPIAnalyzer()
    yield
    analyzers_registry.ANALYZER_REGISTRY.pop("api_dummy", None)


@pytest.mark.asyncio
async def test_monitoring_api_unauthenticated(async_client: AsyncClient, test_user_repository: Repository):
    response = await async_client.post(
        f"/api/v1/repositories/{test_user_repository.id}/monitor-runs",
        json={"analyzer_key": "api_dummy"}
    )
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_monitoring_api_not_found_or_unowned(authorized_client: AsyncClient):
    fake_id = str(uuid.uuid4())
    response = await authorized_client.post(
        f"/api/v1/repositories/{fake_id}/monitor-runs",
        json={"analyzer_key": "api_dummy"}
    )
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_monitoring_api_malformed(authorized_client: AsyncClient, test_user_repository: Repository):
    response = await authorized_client.post(
        f"/api/v1/repositories/{test_user_repository.id}/monitor-runs",
        json={} # Missing required analyzer_key
    )
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_monitoring_api_success(db_session, authorized_client: AsyncClient, test_user_repository: Repository):
    test_user_repository.monitoring_enabled = True
    db_session.commit()
    
    response = await authorized_client.post(
        f"/api/v1/repositories/{test_user_repository.id}/monitor-runs",
        json={"analyzer_key": "api_dummy"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["findings_created"]) == 1
    assert data["findings_created"][0]["title"] == "Test finding via API"

@pytest.mark.asyncio
async def test_monitoring_api_skipped_disabled(db_session, authorized_client: AsyncClient, test_user_repository: Repository):
    test_user_repository.monitoring_enabled = False
    db_session.commit()
    
    response = await authorized_client.post(
        f"/api/v1/repositories/{test_user_repository.id}/monitor-runs",
        json={"analyzer_key": "api_dummy"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "skipped"
    assert data["reason"] == "monitoring_disabled"

@pytest.mark.asyncio
@patch("app.monitoring.monitor_service.GitHubAppClient")
async def test_monitoring_api_dependency_analyzer(mock_client_class, db_session, authorized_client: AsyncClient, test_user_repository: Repository):
    test_user_repository.monitoring_enabled = True
    db_session.commit()
    
    mock_client_instance = AsyncMock()
    mock_client_instance.__aenter__.return_value = mock_client_instance
    mock_client_class.return_value = mock_client_instance
    
    async def get_content(full_name, path):
        if path == "package.json":
            return {"name": "test"}
        return None

    mock_client_instance.get_repository_content.side_effect = get_content
    
    response = await authorized_client.post(
        f"/api/v1/repositories/{test_user_repository.id}/monitor-runs",
        json={"analyzer_key": "dependency"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["findings_created"]) == 1
    assert data["findings_created"][0]["type"] == "missing_lockfile"
    mock_client_class.assert_called_once_with(installation_id=test_user_repository.connection.installation_id)
