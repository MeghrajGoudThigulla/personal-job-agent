import logging
import re
from datetime import datetime
from typing import Dict, Any
from app.config import settings
from app.notifiers.telegram import TelegramNotifier
from app.notifiers.discord import DiscordNotifier
from app.notifiers.slack import SlackNotifier
from app.notifiers.email_notifier import EmailNotifier
from app.intelligence.stair_matcher import StairMatcher

logger = logging.getLogger("personal_job_agent.notifier.dispatcher")

class NotificationDispatcher:
    """Dispatches notifications across all enabled channels simultaneously."""

    def __init__(self):
        self.telegram = TelegramNotifier()
        self.discord = DiscordNotifier()
        self.slack = SlackNotifier()
        self.email = EmailNotifier()
        self.matcher = StairMatcher()

    def is_india_eligible(self, job_data: Dict[str, Any]) -> bool:
        """Enforces candidate preference: strictly Indian jobs (work from office, hybrid, or remote from India)."""
        loc = job_data.get("location") or ""
        desc = job_data.get("description") or ""
        title = job_data.get("title") or ""
        is_eligible, _, _, _ = self.matcher.evaluate_location(loc, desc, title=title)
        return is_eligible

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
