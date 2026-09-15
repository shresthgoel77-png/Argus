from datetime import datetime

from pydantic import BaseModel


class AIConnectionCreate(BaseModel):
    provider: str
    model: str
    api_key: str


class AIConnectionStatus(BaseModel):
    configured: bool
    provider: str
    model: str
    status: str
    last_validated_at: datetime


class AIConnectionNotConfigured(BaseModel):
    configured: bool = False
