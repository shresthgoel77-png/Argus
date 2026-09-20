from pydantic import BaseModel, Field

class CategoryDelta(BaseModel):
    category: str
    delta: int

class HealthTrend(BaseModel):
    overall_delta: int
    category_deltas: list[CategoryDelta]

class CategoryVelocity(BaseModel):
    category: str
    detected: int
    resolved: int

class FindingVelocity(BaseModel):
    categories: list[CategoryVelocity]

class TrendResponse(BaseModel):
    window_days: int
    health_trend: HealthTrend
    finding_velocity: FindingVelocity
