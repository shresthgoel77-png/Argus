import uuid
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict


class FindingBase(BaseModel):
    category: str
    type: str
    title: str
    description: str
    severity: str
    source: str
    evidence: dict[str, Any]


class FindingResponse(FindingBase):
    id: uuid.UUID
    repository_id: uuid.UUID
    status: str
    detected_at: datetime
    updated_at: datetime
    priority: str | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    resolution_source: str | None = None
    
    model_config = ConfigDict(from_attributes=True)


class FindingListResponse(BaseModel):
    items: list[FindingResponse]
    total: int
    limit: int
    offset: int


class FindingStatusUpdateRequest(BaseModel):
    status: Literal["acknowledged", "resolved", "ignored", "open"]
