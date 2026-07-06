from functools import lru_cache
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    APP_NAME: str = "AI Chief of Staff"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    SECRET_KEY: str
    ADMIN_SECRET: str
    TIMEZONE: str = "UTC"

    # ── Admin user ───────────────────────────────────────────────────────────
    ADMIN_PHONE_NUMBER: str

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str

    # ── Redis ────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://redis:6379/0"
    REDIS_CONTEXT_TTL: int = 86400
    REDIS_CONTEXT_MAX_MESSAGES: int = 20

    # ── Qdrant ───────────────────────────────────────────────────────────────
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_MEMORY_COLLECTION: str = "memories"
    QDRANT_KNOWLEDGE_COLLECTION: str = "knowledge"

    # ── Ollama ───────────────────────────────────────────────────────────────
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_DEFAULT_MODEL: str = "qwen3:latest"
    OLLAMA_FAST_MODEL: str = "mistral:latest"
    OLLAMA_REASONING_MODEL: str = "deepseek-r1:latest"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text:latest"
    OLLAMA_TIMEOUT: int = 120

    # ── WhatsApp ─────────────────────────────────────────────────────────────
    WHATSAPP_API_TOKEN: str
    WHATSAPP_PHONE_NUMBER_ID: str
    WHATSAPP_VERIFY_TOKEN: str
    WHATSAPP_APP_SECRET: str
    WHATSAPP_API_VERSION: str = "v18.0"

    # ── Whisper ──────────────────────────────────────────────────────────────
    WHISPER_MODEL_SIZE: str = "base"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"

    # ── JWT ──────────────────────────────────────────────────────────────────
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # ── Backend public URL (used in OAuth redirects and agent messages) ────────
    BACKEND_URL: str = "http://localhost:8000"

    # ── Email — Phase 2 ──────────────────────────────────────────────────────
    GMAIL_CLIENT_ID: Optional[str] = None
    GMAIL_CLIENT_SECRET: Optional[str] = None
    GMAIL_REDIRECT_URI: str = "http://localhost:8000/api/v1/email/auth/gmail/callback"
    OUTLOOK_CLIENT_ID: Optional[str] = None
    OUTLOOK_CLIENT_SECRET: Optional[str] = None
    OUTLOOK_REDIRECT_URI: str = "http://localhost:8000/api/v1/email/auth/outlook/callback"
    OUTLOOK_TENANT_ID: str = "common"

    # ── Research Agent (Phase 5) ─────────────────────────────────────────────
    BRAVE_SEARCH_API_KEY: Optional[str] = None

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith(("postgresql", "sqlite")):
            raise ValueError("DATABASE_URL must be a PostgreSQL or SQLite connection string")
        return v

    def validate_required(self) -> None:
        required = [
            "SECRET_KEY",
            "DATABASE_URL",
            "WHATSAPP_API_TOKEN",
            "WHATSAPP_PHONE_NUMBER_ID",
            "WHATSAPP_VERIFY_TOKEN",
            "WHATSAPP_APP_SECRET",
            "ADMIN_PHONE_NUMBER",
            "ADMIN_SECRET",
        ]
        missing = [var for var in required if not getattr(self, var, None)]
        if missing:
            raise RuntimeError(
                f"Missing required environment variables: {', '.join(missing)}. "
                f"Copy .env.example to .env and fill in all required values."
            )

    @property
    def whatsapp_api_url(self) -> str:
        return f"https://graph.facebook.com/{self.WHATSAPP_API_VERSION}"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT in ("development", "dev", "local")


@lru_cache
def get_settings() -> Settings:
    return Settings()
