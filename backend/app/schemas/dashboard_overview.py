import uuid
from pydantic import BaseModel, ConfigDict
from app.schemas.health import HealthSnapshotResponse
from app.schemas.finding import FindingResponse
from app.schemas.activity import ActivityItem
from app.schemas.ai_analysis import AIAnalysisResponse, AIAnalysisNotExists
from app.schemas.trend import TrendResponse

class NeedsAttentionResponse(BaseModel):
    findings: list[FindingResponse]
    health_snapshot: HealthSnapshotResponse | None
    reasons: list[str]

    model_config = ConfigDict(from_attributes=True)

class DashboardOverviewResponse(BaseModel):
    repository_id: uuid.UUID
    health: HealthSnapshotResponse | None
    needs_attention: NeedsAttentionResponse
    activity_feed: list[ActivityItem]
    ai_summary: AIAnalysisResponse | AIAnalysisNotExists
    trends: TrendResponse
    finding_category_counts: dict[str, int]
