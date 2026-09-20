import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class ActivitySource(str, Enum):
    github_event = "github_event"
    finding_detected = "finding_detected"
    finding_resolved = "finding_resolved"
    health_changed = "health_changed"
    bot_interaction = "bot_interaction"


class ActivityItem(BaseModel):
    source: ActivitySource
    timestamp: datetime
    title: str
    summary: str
    reference_id: uuid.UUID
    details: dict | None = None


class ActivityFeedResponse(BaseModel):
    items: list[ActivityItem]
    next_before: datetime | None = None