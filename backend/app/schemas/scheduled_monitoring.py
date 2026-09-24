from pydantic import BaseModel


class ScheduledMonitoringRunSummary(BaseModel):
    correlation_id: str
    attempted: int
    succeeded: int
    partially_failed: int
    fully_failed: int
    skipped: int
    total_duration: float
