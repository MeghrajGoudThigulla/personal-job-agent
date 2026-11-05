import logging
from datetime import datetime
from typing import Dict, Any
from app.config import settings
from app.notifiers.telegram import TelegramNotifier
from app.notifiers.discord import DiscordNotifier
from app.notifiers.slack import SlackNotifier
from app.notifiers.email_notifier import EmailNotifier

logger = logging.getLogger("personal_job_agent.notifier.dispatcher")

class NotificationDispatcher:
    """Dispatches notifications across all enabled channels simultaneously."""

    def __init__(self):
        self.telegram = TelegramNotifier()
        self.discord = DiscordNotifier()
        self.slack = SlackNotifier()
        self.email = EmailNotifier()

    async def dispatch_job_alert(self, job_data: Dict[str, Any]) -> bool:
        score = job_data.get("match_score", 0.0)
        
        # Only notify if score meets or exceeds minimum threshold
        if score < settings.MIN_MATCH_SCORE_NOTIFY:
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
