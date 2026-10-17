import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, field_validator
from app.schemas.repository import RepositoryCheckStatus


class ExcludedHealthCategory(BaseModel):
    status: str
    reason: str


class HealthCoverage(BaseModel):
    assessed_categories: list[str]
    excluded_categories: dict[str, ExcludedHealthCategory]
    checks: dict[str, RepositoryCheckStatus]

class HealthSnapshotResponse(BaseModel):
    overall_score: int
    category_scores: dict[str, int]
    reasons: list[str]
    computed_at: datetime
    previous_score: int | None = None
    coverage: HealthCoverage | None = None

    @field_validator("computed_at")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

    model_config = ConfigDict(from_attributes=True)


class HealthSnapshotListResponse(BaseModel):
    items: list[HealthSnapshotResponse]
    total: int
    limit: int
    offset: int
