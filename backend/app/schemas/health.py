import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class HealthSnapshotResponse(BaseModel):
    overall_score: int
    category_scores: dict[str, int]
    reasons: list[str]
    computed_at: datetime
    previous_score: int | None = None

    model_config = ConfigDict(from_attributes=True)


class HealthSnapshotListResponse(BaseModel):
    items: list[HealthSnapshotResponse]
    total: int
    limit: int
    offset: int
