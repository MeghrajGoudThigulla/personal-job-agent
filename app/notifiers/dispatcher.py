import logging
import re
from datetime import datetime
from typing import Dict, Any
from app.config import settings
from app.notifiers.telegram import TelegramNotifier
from app.notifiers.discord import DiscordNotifier
from app.notifiers.slack import SlackNotifier
from app.notifiers.email_notifier import EmailNotifier

logger = logging.getLogger("personal_job_agent.notifier.dispatcher")

INDIA_CITIES = [
    "india", "hyderabad", "bengaluru", "bangalore", "pune", "mumbai",
    "gurgaon", "gurugram", "noida", "delhi", "new delhi", "chennai",
    "coimbatore", "ahmedabad", "kolkata", "chandigarh", "kochi",
    "kerala", "karnataka", "telangana", "maharashtra", "tamil nadu",
    "mysore", "indore", "jaipur"
]

class NotificationDispatcher:
    """Dispatches notifications across all enabled channels simultaneously."""

    def __init__(self):
        self.telegram = TelegramNotifier()
        self.discord = DiscordNotifier()
        self.slack = SlackNotifier()
        self.email = EmailNotifier()

    @staticmethod
    def is_india_eligible(job_data: Dict[str, Any]) -> bool:
        """Enforces candidate preference: strictly Indian jobs (onsite or remote from India)."""
        loc = (job_data.get("location") or "").lower()
        desc = (job_data.get("description") or "")[:500].lower()
        title = (job_data.get("title") or "").lower()

        # Reject foreign regional shifts in title
        if re.search(r"\b(emea|amer|americas|latam|europe|us|uk)\b", title) and not re.search(r"\b(india)\b", title):
            return False

        # Reject explicitly non-India locations
        if any(f in loc for f in ["united states", "north america", "europe", "emea", "amer", "poland", "germany", "uk", "canada"]):
            if not any(ind in loc for ind in INDIA_CITIES):
                return False

        # Match any Indian city or state or 'india'
        if any(ind in loc for ind in INDIA_CITIES):
            return True

        # Check description
        if any(ind in desc for ind in ["india", "bengaluru", "bangalore", "hyderabad", "pune"]):
            return True

        return False

    async def dispatch_job_alert(self, job_data: Dict[str, Any]) -> bool:
        score = job_data.get("match_score", 0.0)
        
        # Hard check: Only notify if score meets or exceeds minimum threshold
        if score < settings.MIN_MATCH_SCORE_NOTIFY:
            return False

        # Hard check: Strictly India Only
        if not self.is_india_eligible(job_data):
            logger.info(f"Notification skipped for '{job_data.get('title')}': Location '{job_data.get('location')}' is not India.")
            return False

        notified_any = False

        # Telegram
        if self.telegram.is_configured:
            ok = await self.telegram.send_job_alert(job_data)
            if ok:
                notified_any = True

        # Discord
        if self.discord.is_configured:
            ok = await self.discord.send_job_alert(job_data)
            if ok:
                notified_any = True

        # Slack
        if self.slack.is_configured:
            ok = await self.slack.send_job_alert(job_data)
            if ok:
                notified_any = True

        # Email
        if self.email.is_configured:
            ok = await self.email.send_job_alert(job_data)
            if ok:
                notified_any = True

        if not notified_any:
            logger.info(f"No external notification channels configured or fired for {job_data.get('title')}. Alert recorded in database.")

        return notified_any
