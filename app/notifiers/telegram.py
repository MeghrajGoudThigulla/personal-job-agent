import logging
import httpx
from typing import Dict, Any, Optional
from app.config import settings
from app.core.trace import log_audit_event

logger = logging.getLogger("personal_job_agent.notifier.telegram")

class TelegramNotifier:
    """Sends real-time job alerts to Meghraj via Telegram Bot."""

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self._override_token = bot_token
        self._override_chat_id = chat_id

    @property
    def bot_token(self) -> str:
        return self._override_token or settings.TELEGRAM_BOT_TOKEN

    @property
    def chat_id(self) -> str:
        return self._override_chat_id or settings.TELEGRAM_CHAT_ID

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    async def send_job_alert(self, job_data: Dict[str, Any]) -> bool:
        if not self.is_configured:
            return False

        title = job_data.get("title", "Untitled Role")
        company = job_data.get("company", "Unknown Company")
        location = job_data.get("location", "Remote")
        match_score = job_data.get("match_score", 0.0)
        match_tier = job_data.get("match_tier", "P1")
        role_category = job_data.get("role_category", "Engineering")
        url = job_data.get("url", "")
        matched_skills = job_data.get("matched_skills", [])
        job_id = job_data.get("id", "")

        skills_str = ", ".join(matched_skills[:6]) if matched_skills else "Python, Backend"

        text = (
            f"🚀 *NEW HIGH-MATCH JOB DISCOVERED*\n\n"
            f"🏢 *Company:* {company}\n"
            f"💼 *Role:* {title}\n"
            f"📍 *Location:* {location}\n"
            f"🎯 *Match Score:* `{match_score}%` ({match_tier})\n"
            f"🏷️ *Category:* {role_category}\n"
            f"🛠️ *Stack Match:* {skills_str}\n\n"
            f"🔗 [Direct Apply Link]({url})\n"
        )

        api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(api_url, json=payload)
                res.raise_for_status()
                await log_audit_event("telegram_notification", {"job_id": job_id, "company": company}, "success")
                return True
        except Exception as e:
            raw_err = str(e)
            token = self.bot_token
            sanitized_err = raw_err.replace(token, "[REDACTED_BOT_TOKEN]") if token else raw_err
            logger.error(f"Failed to send Telegram notification: {sanitized_err}")
            await log_audit_event("telegram_notification", {"job_id": job_id, "error": sanitized_err}, "error")
            return False
