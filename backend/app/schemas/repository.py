import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class RepositoryRead(BaseModel):
    id: uuid.UUID
    full_name: str
    private: bool
    default_branch: str | None = None
    monitoring_enabled: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AvailableRepository(BaseModel):
    github_repo_id: int
    full_name: str
    private: bool
    default_branch: str | None = None
    already_added: bool


class RepositoryCreate(BaseModel):
    connection_id: uuid.UUID
    github_repo_id: int


class RepositoryUpdate(BaseModel):
    monitoring_enabled: bool
