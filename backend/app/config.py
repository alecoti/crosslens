from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash-preview-tts"
    static_dir: Path = Path("backend/static")
    allowed_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    model_config = SettingsConfigDict(env_prefix="podcastfy_", env_file=".env", extra="allow")


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    settings.static_dir.mkdir(parents=True, exist_ok=True)
    return settings
