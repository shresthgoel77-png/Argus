from typing import Literal, Any, List, Union
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str
    test_database_url: str | None = None
    log_level: str = "INFO"
    cors_origins: Union[List[str], str] = ["http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> Any:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    @model_validator(mode="after")
    def validate_requirements_for_env(self) -> 'Settings':
        if self.app_env != "development":
            if not self.database_url:
                raise ValueError("DATABASE_URL is required and must not be empty in non-development environments")
        return self

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8', extra='ignore')

settings = Settings()
