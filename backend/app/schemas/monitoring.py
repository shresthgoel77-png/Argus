from pydantic import BaseModel
from typing import Optional

class FindingSummary(BaseModel):
    id: str
    category: str
    type: str
    title: str
    severity: str

class MonitorRunRequest(BaseModel):
    analyzer_key: str

class MonitorRunResult(BaseModel):
    status: str
    reason: Optional[str] = None
    error_message: Optional[str] = None
    findings_created: list[FindingSummary] = []
