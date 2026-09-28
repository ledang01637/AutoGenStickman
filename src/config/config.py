# src/config/config.py

from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DATA_DIR = Path.home() / ".browser2api"


class Settings(BaseSettings):
    # ── AI APIs ───────────────────────────────────────────
    CHATGPT_API_KEY: str
    GEMINI_API_KEY: str
    ANTHROPIC_API_KEY: str
    FAL_KEY: str

    # ── Voice ─────────────────────────────────────────────
    VBEE_API_KEY: str
    VBEE_APP_ID: str

    # ── Database ──────────────────────────────────────────
    DATABASE_URL: str

    # ── Cache / Queue ─────────────────────────────────────
    REDIS_URL: str = "redis://redis:6379/0"   

    # ── App ───────────────────────────────────────────────
    APP_ENV: str = "development"           
    APP_NAME: str = "autogen"                

    # ── Auth / Session ────────────────────────────────────
    SECRET_KEY: str
    COOKIE_SECURE: bool = True
    COOKIE_SAMESITE: str = "lax"

    # ── Google OAuth ──────────────────────────────────────
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str

    # ENV
    ENV: str  # "production" in prod

    # ── Origin ─────────────────────────────────────────────
    ALLOWED_ORIGINS: str = ""
    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod  
    def parse_origins(cls, v):
        if isinstance(v, str):
            return v 
        return v

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    # ── PayOS ─────────────────────────────────────────────
    PAYOS_CLIENT_ID: str
    PAYOS_API_KEY: str
    PAYOS_CHECKSUM_KEY: str
    PAYOS_RETURN_URL: str
    PAYOS_CANCEL_URL: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",                      
    )

    # ── URLs ──────────────────────────────────────────────
    CLIENT_URL: str = "http://localhost"


settings = Settings()