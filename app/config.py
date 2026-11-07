import os
from pathlib import Path
from typing import Any
from pydantic import field_validator
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

class Settings(BaseSettings):
    APP_NAME: str = "Personal Job Agent"
    ENV: str = "production"
    DEBUG: bool = False
    PORT: int = int(os.getenv("PORT", 8000))
    HOST: str = "0.0.0.0"

    # Storage
    DATABASE_URL: str = f"sqlite+aiosqlite:///{DATA_DIR}/jobs.db"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: Any) -> str:
        if not v:
            return f"sqlite+aiosqlite:///{DATA_DIR}/jobs.db"
        val = str(v).strip()
        if val.startswith("postgres://"):
            return val.replace("postgres://", "postgresql+asyncpg://", 1)
        elif val.startswith("postgresql://") and not val.startswith("postgresql+asyncpg://"):
            return val.replace("postgresql://", "postgresql+asyncpg://", 1)
        return val

    # Security & Single-User Auth
    APP_PASSWORD: str = os.getenv("APP_PASSWORD", "")
    ADMIN_SESSION_COOKIE: str = "pja_session"

    # Scheduler & Data Retention
    SCHEDULER_ENABLED: bool = True
    SCRAPE_INTERVAL_MINUTES: int = 60
    AUTO_TAILOR_HIGH_MATCH: bool = True
    MIN_MATCH_SCORE_NOTIFY: int = 70
    DATA_RETENTION_DAYS: int = int(os.getenv("DATA_RETENTION_DAYS", "60"))
    AUTO_CLEANUP_ENABLED: bool = os.getenv("AUTO_CLEANUP_ENABLED", "true").lower() in ("true", "1")

    # LLM Configuration
    # Options: "auto" (Groq <-> NVIDIA NIM auto-failover), "groq", "nvidia"
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "auto")

    # Groq Settings
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    # NVIDIA NIM Settings (e.g. nvidia/nemotron-3-ultra-550b-a55b or meta/llama-3.1-70b-instruct)
    NVIDIA_NIM_API_KEY: str = os.getenv("NVIDIA_NIM_API_KEY", "")
    NVIDIA_NIM_MODEL: str = os.getenv("NVIDIA_NIM_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")
    NVIDIA_NIM_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

    # Notification Channels
    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Discord Webhook
    DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")

    # Slack Webhook
    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")

    # Email / SMTP
    EMAIL_NOTIFY_ENABLED: bool = False
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASS: str = os.getenv("SMTP_PASS", "")
    SMTP_TO: str = os.getenv("SMTP_TO", "meghraj.thigulla@outlook.com")

    # Paths
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = DATA_DIR
    BASE_RESUME_TEX: Path = DATA_DIR / "base_resume.tex"
    BASE_RESUME_MD: Path = DATA_DIR / "base_resume.md"
    CANDIDATE_PROFILE_JSON: Path = DATA_DIR / "candidate_profile.json"
    PERSONALIZED_QUERIES_JSON: Path = DATA_DIR / "personalized_queries.json"
    COMPANY_TARGETS_JSON: Path = DATA_DIR / "company_targets.json"
    COLD_TEMPLATES_JSON: Path = DATA_DIR / "cold_outreach_templates.json"
    ANTI_SLOP_RULES_JSON: Path = DATA_DIR / "anti_slop_rules.json"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

settings = Settings()

