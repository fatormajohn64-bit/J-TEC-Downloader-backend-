"""
J TEC Downloader
Application configuration.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # -----------------------------------------------------
    # APPLICATION
    # -----------------------------------------------------

    app_name: str = "J TEC Downloader"
    app_version: str = "1.0.0"
    debug: bool = False

    # -----------------------------------------------------
    # SERVER
    # -----------------------------------------------------

    host: str = "0.0.0.0"
    port: int = 8000

    # -----------------------------------------------------
    # STORAGE
    # -----------------------------------------------------

    temp_download_dir: str = "temp_downloads"

    # -----------------------------------------------------
    # DOWNLOAD LIMITS
    # -----------------------------------------------------

    max_video_duration: int = 3600
    cleanup_after_seconds: int = 300

    # -----------------------------------------------------
    # CORS
    # -----------------------------------------------------

    allowed_origins: str = "*"

    # -----------------------------------------------------
    # SETTINGS FILE
    # -----------------------------------------------------

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Return a cached application settings instance.
    """
    return Settings()


settings = get_settings()
