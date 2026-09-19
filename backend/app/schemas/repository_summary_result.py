from pydantic import BaseModel, Field


class RepositorySummaryResult(BaseModel):
    summary: str
    key_insights: list[str]
    recommendations: list[str]
    confidence: float = Field(ge=0.0, le=1.0)