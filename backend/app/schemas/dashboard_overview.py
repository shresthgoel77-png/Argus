import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, field_validator
from app.schemas.health import HealthSnapshotResponse
from app.schemas.finding import FindingResponse
from app.schemas.activity import ActivityItem
from app.schemas.ai_analysis import AIAnalysisResponse, AIAnalysisNotExists
from app.schemas.trend import TrendResponse
from app.schemas.repository import RepositoryCheckStatus

class NeedsAttentionResponse(BaseModel):
    findings: list[FindingResponse]
    health_snapshot: HealthSnapshotResponse | None
    reasons: list[str]

    model_config = ConfigDict(from_attributes=True)

class DashboardOverviewResponse(BaseModel):
    repository_id: uuid.UUID
    health: HealthSnapshotResponse | None
    last_recorded_health: HealthSnapshotResponse | None = None
    needs_attention: NeedsAttentionResponse
    activity_feed: list[ActivityItem]
    ai_summary: AIAnalysisResponse | AIAnalysisNotExists
    trends: TrendResponse
    finding_category_counts: dict[str, int]
    monitoring_status: str
    monitoring_checks: dict[str, RepositoryCheckStatus]
    last_monitoring_at: datetime | None

    @field_validator("last_monitoring_at")
    @classmethod
    def utc_timestamp(cls, value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value
