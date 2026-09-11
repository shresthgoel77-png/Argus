import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class GitHubConnectionRead(BaseModel):
    id: uuid.UUID
    installation_id: int
    account_login: str
    account_type: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
