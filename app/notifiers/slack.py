import logging
import httpx
from typing import Dict, Any, Optional
from app.config import settings

logger = logging.getLogger("personal_job_agent.notifier.slack")

class SlackNotifier:
    """Sends Slack block alerts."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.SLACK_WEBHOOK_URL

    @property
    def is_configured(self) -> bool:
        return bool(self.webhook_url and self.webhook_url.startswith("http"))

    async def send_job_alert(self, job_data: Dict[str, Any]) -> bool:
        if not self.is_configured:
            return False

        title = job_data.get("title", "Role")
        company = job_data.get("company", "Company")
        url = job_data.get("url", "")
        match_score = job_data.get("match_score", 0.0)

        payload = {
            "text": f"🎯 *New Job Alert:* <{url}|{title} at {company}> (Match: {match_score}%)"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(self.webhook_url, json=payload)
                res.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False
