from typing import Literal, Any, List, Union
from pydantic import Field, field_validator, model_validator, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: Literal["development", "test", "production"] = "development"
    auth_provider: Literal["development", "clerk"] = "development"
    session_secret_key: str = "dev_secret_key_change_me_in_production"
    database_url: str
    test_database_url: str | None = None
    log_level: str = "INFO"
    cors_origins: Union[List[str], str] = ["http://localhost:3000"]
    api_rate_limit_requests: int = Field(default=120, gt=0)
    api_rate_limit_window_seconds: int = Field(default=60, gt=0)

    github_app_id: str
    github_app_slug: str
    github_app_private_key: SecretStr
    github_app_webhook_secret: SecretStr
    github_app_install_state_ttl_seconds: int = 600
    ai_credential_encryption_key: SecretStr
    scheduler_shared_secret: SecretStr | None = None

    # Clerk auth config (required when auth_provider == "clerk")
    clerk_secret_key: SecretStr | None = None
    clerk_jwt_key: str | None = None
    clerk_authorized_parties: List[str] | None = None

    bot_mention_handle: str = "@repomedic"
    bot_max_interactions_per_hour: int = 10
    health_drop_notification_threshold: int = 15
    stale_issue_days: int = 30
    stale_pr_days: int = 14

    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_address: str | None = None
    smtp_use_tls: bool = True

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

    @field_validator("clerk_authorized_parties", mode="before")
    @classmethod
    def assemble_clerk_authorized_parties(cls, v: Any) -> Any:
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
            raise ValueError(
                "GITHUB_APP_SLUG is required and "
                "must not be empty"
            )
        if (not self.github_app_private_key or
                not self.github_app_private_key.get_secret_value()):
            raise ValueError(
                "GITHUB_APP_PRIVATE_KEY is required and "
                "must not be empty"
            )
        if (not self.github_app_webhook_secret or
                not self.github_app_webhook_secret.get_secret_value()):
            raise ValueError(
                "GITHUB_APP_WEBHOOK_SECRET is required and "
                "must not be empty"
            )

        if (not self.ai_credential_encryption_key or
                not self.ai_credential_encryption_key.get_secret_value()):
            raise ValueError(
                "AI_CREDENTIAL_ENCRYPTION_KEY is required and "
                "must not be empty"
            )

        from cryptography.fernet import Fernet
        try:
            Fernet(self.ai_credential_encryption_key.get_secret_value())
        except Exception:
            raise ValueError(
                "AI_CREDENTIAL_ENCRYPTION_KEY is malformed, "
                "must be a valid Fernet key"
            )

        if self.app_env != "development":
            if not self.database_url:
                raise ValueError(
                    "DATABASE_URL is required and "
                    "must not be empty in non-development environments"
                )

        if self.app_env == "production":
            if (not self.scheduler_shared_secret or
                    not self.scheduler_shared_secret.get_secret_value()):
                raise ValueError(
                    "SCHEDULER_SHARED_SECRET is required and "
                    "must not be empty in production environment"
                )
            if self.auth_provider == "development":
                raise ValueError(
                    "Development auth provider cannot be "
                    "used in production environment"
                )
            if self.auth_provider == "clerk":
                if (
                    (not self.clerk_secret_key or
                     not self.clerk_secret_key.get_secret_value())
                    and not self.clerk_jwt_key
                ):
                    raise ValueError(
                        "Clerk auth requires CLERK_SECRET_KEY or "
                        "CLERK_JWT_KEY in production environment"
                    )
            if (
                self.session_secret_key ==
                "dev_secret_key_change_me_in_production"
            ):
                raise ValueError(
                    "SESSION_SECRET_KEY must be overridden "
                    "in production environment"
                )
            if "cors_origins" not in self.model_fields_set:
                raise ValueError(
                    "CORS_ORIGINS must be explicitly configured in production"
                )
            if not self.cors_origins or "*" in self.cors_origins:
                raise ValueError(
                    "CORS_ORIGINS must contain explicit origins in production"
                )
            if not self.clerk_authorized_parties:
                raise ValueError(
                    "CLERK_AUTHORIZED_PARTIES must be explicitly configured in production"
                )
            if "*" in self.clerk_authorized_parties:
                raise ValueError(
                    "CLERK_AUTHORIZED_PARTIES must contain explicit origins in production"
                )

        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        extra='ignore')


settings = Settings()  # type: ignore[call-arg]
