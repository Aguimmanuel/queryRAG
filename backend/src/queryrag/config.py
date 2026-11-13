from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    max_evidence_distance: float = 0.5
    max_upload_mb: int = 10

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
