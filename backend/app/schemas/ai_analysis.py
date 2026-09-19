import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, field_validator


class AIAnalysisResponse(BaseModel):
    id: uuid.UUID
    finding_id: uuid.UUID | None = None
    repository_id: uuid.UUID | None = None
    analysis_type: Literal["finding_explanation", "repository_summary"] = "finding_explanation"
    provider: str
    model: str
    status: str
    requested_at: datetime
    completed_at: datetime | None = None
    summary: str | None = None
    severity_assessment: str | None = None
    confidence: str | None = None
    recommendations: str | None = None

    @field_validator("finding_id", "repository_id", mode="before")
    @classmethod
    def validate_scope_id(cls, value: object) -> uuid.UUID | None:
        return value if value is None or isinstance(value, uuid.UUID) else None

    @field_validator("analysis_type", mode="before")
    @classmethod
    def validate_analysis_type(cls, value: object) -> str:
        return value if isinstance(value, str) else "finding_explanation"

    model_config = ConfigDict(from_attributes=True)


class AIAnalysisNotExists(BaseModel):
    exists: bool = False


class AIAnalysisHistoryResponse(BaseModel):
    items: list[AIAnalysisResponse]
    total: int
    limit: int
    offset: int
