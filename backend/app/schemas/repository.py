import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class RepositoryCheckStatus(BaseModel):
    status: str
    error_message: str | None = None
    checked_at: datetime | None = None


class GitHubWorkItem(BaseModel):
    number: int
    title: str
    state: str
    html_url: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    user: dict[str, object] | None = None
    labels: list[dict[str, object]] = Field(default_factory=list)
    draft: bool | None = None


class RepositoryRead(BaseModel):
    id: uuid.UUID
    full_name: str
    private: bool
    default_branch: str | None = None
    monitoring_enabled: bool
    monitoring_status: str
    monitoring_checks: dict[str, RepositoryCheckStatus]
    last_monitoring_at: datetime | None
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
