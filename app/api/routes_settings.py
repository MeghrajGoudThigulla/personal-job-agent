from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import settings
from app.core.database import get_db
from app.core.models import AppSetting
from app.core.trace import log_audit_event

router = APIRouter(prefix="/api/settings", tags=["Settings"])

class SettingsUpdate(BaseModel):
    llm_provider: Optional[str] = None
    groq_api_key: Optional[str] = None
    groq_model: Optional[str] = None
    nvidia_nim_api_key: Optional[str] = None
    nvidia_nim_model: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    discord_webhook_url: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    min_match_score_notify: Optional[int] = None
    scrape_interval_minutes: Optional[int] = None
    jobspy_sites: Optional[str] = None
    jobspy_results_wanted: Optional[int] = None
    jobspy_proxies: Optional[str] = None

@router.get("")
async def get_current_settings(db: AsyncSession = Depends(get_db)):
    def mask(val: str) -> str:
        if not val or len(val) < 8:
            return "" if not val else "********"
        return f"{val[:4]}...{val[-4:]}"

    return {
        "llm_provider": settings.LLM_PROVIDER,
        "groq_api_key_masked": mask(settings.GROQ_API_KEY),
        "groq_model": settings.GROQ_MODEL,
        "nvidia_nim_api_key_masked": mask(settings.NVIDIA_NIM_API_KEY),
        "nvidia_nim_model": settings.NVIDIA_NIM_MODEL,
        "telegram_bot_token_masked": mask(settings.TELEGRAM_BOT_TOKEN),
        "telegram_chat_id_masked": mask(settings.TELEGRAM_CHAT_ID),
        "discord_webhook_url_masked": mask(settings.DISCORD_WEBHOOK_URL),
        "slack_webhook_url_masked": mask(settings.SLACK_WEBHOOK_URL),
        "min_match_score_notify": settings.MIN_MATCH_SCORE_NOTIFY,
        "scrape_interval_minutes": settings.SCRAPE_INTERVAL_MINUTES,
        "jobspy_sites": settings.JOBSPY_SITES,
        "jobspy_results_wanted": settings.JOBSPY_RESULTS_WANTED,
        "jobspy_proxies": settings.JOBSPY_PROXIES,
    }

@router.post("")
async def update_settings(payload: SettingsUpdate, db: AsyncSession = Depends(get_db)):
    updated = {}

    if payload.llm_provider is not None:
        settings.LLM_PROVIDER = payload.llm_provider
        updated["LLM_PROVIDER"] = payload.llm_provider
    if payload.groq_api_key is not None and payload.groq_api_key != "":
        settings.GROQ_API_KEY = payload.groq_api_key
        updated["GROQ_API_KEY"] = payload.groq_api_key
    if payload.groq_model is not None:
        settings.GROQ_MODEL = payload.groq_model
        updated["GROQ_MODEL"] = payload.groq_model
    if payload.nvidia_nim_api_key is not None and payload.nvidia_nim_api_key != "":
        settings.NVIDIA_NIM_API_KEY = payload.nvidia_nim_api_key
        updated["NVIDIA_NIM_API_KEY"] = payload.nvidia_nim_api_key
    if payload.nvidia_nim_model is not None:
        settings.NVIDIA_NIM_MODEL = payload.nvidia_nim_model
        updated["NVIDIA_NIM_MODEL"] = payload.nvidia_nim_model
    if payload.telegram_bot_token is not None and payload.telegram_bot_token != "":
        settings.TELEGRAM_BOT_TOKEN = payload.telegram_bot_token
        updated["TELEGRAM_BOT_TOKEN"] = payload.telegram_bot_token
    if payload.telegram_chat_id is not None and payload.telegram_chat_id != "":
        settings.TELEGRAM_CHAT_ID = payload.telegram_chat_id
        updated["TELEGRAM_CHAT_ID"] = payload.telegram_chat_id
    if payload.discord_webhook_url is not None and payload.discord_webhook_url != "":
        settings.DISCORD_WEBHOOK_URL = payload.discord_webhook_url
        updated["DISCORD_WEBHOOK_URL"] = payload.discord_webhook_url
    if payload.slack_webhook_url is not None and payload.slack_webhook_url != "":
        settings.SLACK_WEBHOOK_URL = payload.slack_webhook_url
        updated["SLACK_WEBHOOK_URL"] = payload.slack_webhook_url
    if payload.min_match_score_notify is not None:
        settings.MIN_MATCH_SCORE_NOTIFY = payload.min_match_score_notify
        updated["MIN_MATCH_SCORE_NOTIFY"] = str(payload.min_match_score_notify)
    if payload.scrape_interval_minutes is not None:
        settings.SCRAPE_INTERVAL_MINUTES = payload.scrape_interval_minutes
        updated["SCRAPE_INTERVAL_MINUTES"] = str(payload.scrape_interval_minutes)
    if payload.jobspy_sites is not None:
        settings.JOBSPY_SITES = payload.jobspy_sites
        updated["JOBSPY_SITES"] = payload.jobspy_sites
    if payload.jobspy_results_wanted is not None:
        settings.JOBSPY_RESULTS_WANTED = payload.jobspy_results_wanted
        updated["JOBSPY_RESULTS_WANTED"] = str(payload.jobspy_results_wanted)
    if payload.jobspy_proxies is not None:
        settings.JOBSPY_PROXIES = payload.jobspy_proxies
        updated["JOBSPY_PROXIES"] = payload.jobspy_proxies

    # Persist in DB
    for k, v in updated.items():
        existing = await db.execute(select(AppSetting).where(AppSetting.key == k))
        rec = existing.scalar_one_or_none()
        if not rec:
            db.add(AppSetting(key=k, value=str(v)))
        else:
            rec.value = str(v)

    await db.commit()
    await log_audit_event("settings_updated", {"keys": list(updated.keys())}, "success")

    return {"success": True, "updated_keys": list(updated.keys())}
