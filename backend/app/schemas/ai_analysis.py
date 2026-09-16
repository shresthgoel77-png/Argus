import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AIAnalysisResponse(BaseModel):
    id: uuid.UUID
    finding_id: uuid.UUID
    provider: str
    model: str
    status: str
    requested_at: datetime
    completed_at: datetime | None = None
    summary: str | None = None
    severity_assessment: str | None = None
    confidence: str | None = None
    recommendations: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AIAnalysisNotExists(BaseModel):
    exists: bool = False


class AIAnalysisHistoryResponse(BaseModel):
    items: list[AIAnalysisResponse]
    total: int
    limit: int
    offset: int
