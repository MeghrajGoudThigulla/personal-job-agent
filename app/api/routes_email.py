from fastapi import APIRouter, BackgroundTasks
from sqlalchemy import desc, select
from app.config import settings
from app.core.database import async_session_factory
from app.core.models import SeenEmail
from app.email_monitor.inbox_scanner import InboxScanner

router = APIRouter(prefix="/api/email", tags=["Email Monitor"])
scanner = InboxScanner()


@router.post("/scan")
async def trigger_email_scan(background_tasks: BackgroundTasks):
    """Triggers an immediate scan of Gmail & Outlook inboxes."""
    background_tasks.add_task(scanner.scan_all_accounts)
    return {
        "status": "triggered",
        "message": "Email scan initiated in background. Urgent notifications will be sent to Telegram.",
        "accounts_configured": {
            "gmail": bool(settings.GMAIL_USER and settings.GMAIL_APP_PASSWORD),
            "outlook": bool(settings.OUTLOOK_USER and settings.OUTLOOK_APP_PASSWORD),
        },
    }


@router.get("/recent")
async def get_recent_email_alerts():
    """Returns the most recent candidate emails notified by the agent."""
    async with async_session_factory() as session:
        res = await session.execute(
            select(SeenEmail).order_by(desc(SeenEmail.notified_at)).limit(20)
        )
        records = res.scalars().all()
        return [r.to_dict() for r in records]


@router.get("/summary")
async def get_email_inbox_summary(limit: int = 15):
    """Returns an AI-generated executive summary of all recent candidate recruitment emails."""
    res = await scanner.get_recent_emails_summary(limit=limit)
    return res
