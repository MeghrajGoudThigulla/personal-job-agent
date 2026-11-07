import logging
import httpx
from typing import Dict, Any, Optional
from app.config import settings
from app.core.trace import log_audit_event

logger = logging.getLogger("personal_job_agent.notifier.discord")

class DiscordNotifier:
    """Sends rich Discord embed alerts."""

    def __init__(self, webhook_url: Optional[str] = None):
        self._override_webhook_url = webhook_url

    @property
    def webhook_url(self) -> str:
        return self._override_webhook_url or settings.DISCORD_WEBHOOK_URL

    @property
    def is_configured(self) -> bool:
        return bool(self.webhook_url and self.webhook_url.startswith("http"))

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

        # Color: Green (>=85%), Blue (>=70%), Orange (other)
        color = 0x10B981 if match_score >= 85 else (0x3B82F6 if match_score >= 70 else 0xF59E0B)

        posted_str = job_data.get("posted_at_ist") or job_data.get("posted_date") or "Recently discovered"
        if job_data.get("posted_date_unverified"):
            posted_str += " (unverified date)"

        embed = {
            "title": f"🎯 {title} @ {company}",
            "url": url,
            "description": f"New verified role matching candidate profile ({match_tier}).",
            "color": color,
            "fields": [
                {"name": "Match Score", "value": f"**{match_score}%**", "inline": True},
                {"name": "Tier", "value": match_tier, "inline": True},
                {"name": "Location", "value": location, "inline": True},
                {"name": "Posted", "value": posted_str, "inline": True},
                {"name": "Role Category", "value": role_category, "inline": True},
                {"name": "Matched Skills", "value": ", ".join(matched_skills[:8]) if matched_skills else "Python, Backend", "inline": False}
            ],
            "footer": {"text": "Personal Job Agent • High Priority Alert"}
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(self.webhook_url, json={"embeds": [embed]})
                res.raise_for_status()
                await log_audit_event("discord_notification", {"job_id": job_id, "company": company}, "success")
                return True
        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")
            await log_audit_event("discord_notification", {"job_id": job_id, "error": str(e)}, "error")
            return False
