from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    image_generation_provider: str = "mock"
    openai_api_key: str | None = None
    image_generation_model: str = "gpt-image-2.5-sunburst"
    image_generation_quality: str = "high"
    image_generation_size: str = "1024x1536"
    image_generation_format: str = "png"
    max_upload_size_mb: int = 15
    vision_provider: str = "mock"
    background_removal_provider: str = "mock"
    moderation_provider: str = "mock"
    max_generation_retries: int = 3
    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
