from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    openai_api_key: str | None = None
    openai_model: str = "o4-mini"
    allowed_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    model_config = SettingsConfigDict(env_prefix="crosslens_", env_file=".env", extra="allow")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
