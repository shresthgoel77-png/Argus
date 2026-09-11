from typing import Literal, Any, List, Union
from pydantic import field_validator, model_validator, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: Literal["development", "test", "production"] = "development"
    # To be extended with "clerk" etc. later
    auth_provider: Literal["development"] = "development"
    session_secret_key: str = "dev_secret_key_change_me_in_production"
    database_url: str
    test_database_url: str | None = None
    log_level: str = "INFO"
    cors_origins: Union[List[str], str] = ["http://localhost:3000"]
    
    github_app_id: str
    github_app_slug: str
    github_app_private_key: SecretStr
    github_app_install_state_ttl_seconds: int = 600

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> Any:
        if isinstance(v, str):
            v_stripped = v.strip()
            if v_stripped.startswith("[") and v_stripped.endswith("]"):
                import json
                try:
                    return json.loads(v_stripped)
                except ValueError:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    @model_validator(mode="after")
    def validate_requirements_for_env(self) -> 'Settings':
        if not self.github_app_id:
            raise ValueError("GITHUB_APP_ID is required and must not be empty")
        if not self.github_app_slug:
            raise ValueError("GITHUB_APP_SLUG is required and must not be empty")
        if not self.github_app_private_key or not self.github_app_private_key.get_secret_value():
            raise ValueError("GITHUB_APP_PRIVATE_KEY is required and must not be empty")

        if self.app_env != "development":
            if not self.database_url:
                raise ValueError("DATABASE_URL is required and must not be empty in non-development environments")
        
        if self.app_env == "production":
            if self.auth_provider == "development":
                raise ValueError("Development auth provider cannot be used in production environment")
            if self.session_secret_key == "dev_secret_key_change_me_in_production":
                raise ValueError("SESSION_SECRET_KEY must be overridden in production environment")
                
        return self

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8', extra='ignore')

settings = Settings()
