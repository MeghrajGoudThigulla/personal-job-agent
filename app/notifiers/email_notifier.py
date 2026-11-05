import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any
from app.config import settings

logger = logging.getLogger("personal_job_agent.notifier.email")

class EmailNotifier:
    """Sends email notifications via SMTP."""

    def __init__(self):
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.user = settings.SMTP_USER
        self.password = settings.SMTP_PASS
        self.recipient = settings.SMTP_TO

    @property
    def is_configured(self) -> bool:
        return bool(settings.EMAIL_NOTIFY_ENABLED and self.host and self.user and self.password)

    async def send_job_alert(self, job_data: Dict[str, Any]) -> bool:
        if not self.is_configured:
            return False

        title = job_data.get("title", "")
        company = job_data.get("company", "")
        url = job_data.get("url", "")
        score = job_data.get("match_score", 0.0)

        msg = MIMEMultipart()
        msg["From"] = self.user
        msg["To"] = self.recipient
        msg["Subject"] = f"Job Alert: {title} at {company} ({score}% Match)"

        body = f"Hi Meghraj,\n\nA new matching job was discovered:\n\nRole: {title}\nCompany: {company}\nMatch Score: {score}%\nURL: {url}\n\nGood luck!"
        msg.attach(MIMEText(body, "plain"))

        try:
            with smtplib.SMTP(self.host, self.port) as server:
                server.starttls()
                server.login(self.user, self.password)
                server.send_message(msg)
            return True
        except Exception as e:
            logger.error(f"Email dispatch error: {e}")
            return False
