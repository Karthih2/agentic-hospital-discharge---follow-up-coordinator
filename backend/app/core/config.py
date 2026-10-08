from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore")

    mongo_uri: str = ""
    mongo_db: str = "discharge_coordinator"
    jwt_secret: str = ""
    field_enc_key: str = ""
    groq_api_key: str = ""
    groq_model: str = ""
    claude_api_key: str = ""  # optional fallback when GROQ is not set
    claude_model: str = "claude-sonnet-5-5"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_ids: str = ""  # "en:id,ta:id,hi:id"
    cors_origin: str = "http://localhost:5173"
    max_upload_mb: int = 5
    max_pdf_pages: int = 20
    confidence_threshold: float = 0.70
    cookie_secure: bool = False
    skip_init: bool = False
    review_aging_hours: int = 24
    access_ttl_min: int = 15
    refresh_ttl_days: int = 7

    def validate_secrets(self) -> None:
        if len(self.jwt_secret) < 32:
            raise RuntimeError("JWT_SECRET missing or shorter than 32 chars")
        if not self.field_enc_key:
            raise RuntimeError("FIELD_ENC_KEY missing")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
