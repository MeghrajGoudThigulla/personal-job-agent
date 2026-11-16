from datetime import timedelta
import logging
from typing import Any, Dict
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import settings
from app.core.clock import utcnow
from app.scrapers.engine import ScraperEngine

logger = logging.getLogger("personal_job_agent.scheduler")

scheduler = AsyncIOScheduler()
engine_instance = ScraperEngine()


async def scheduled_scrape_task():
    logger.info("Executing scheduled job discovery task...")
    try:
        await engine_instance.run_discovery_cycle()
    except Exception as e:
        logger.error(f"Error during scheduled scraper run: {e}")


async def scheduled_cleanup_task():
    if not settings.AUTO_CLEANUP_ENABLED:
        return
    logger.info("Executing scheduled data retention cleanup task at 03:00 IST...")
    try:
        from app.core.cleanup import purge_old_records

        await purge_old_records()
    except Exception as e:
        logger.error(f"Error during scheduled data cleanup: {e}")


async def scheduled_digest_task():
    logger.info("Executing scheduled daily job digest at 08:00 IST...")
    try:
        from app.core.database import async_session_factory
        from app.core.models import JobPosting
        from app.notifiers.dispatcher import NotificationDispatcher
        from sqlalchemy import select

        async with async_session_factory() as session:
            res = await session.execute(
                select(JobPosting)
                .where(JobPosting.match_score >= settings.MIN_MATCH_SCORE_NOTIFY)
                .order_by(JobPosting.discovered_at.desc())
                .limit(5)
            )
            top_jobs = res.scalars().all()
            if top_jobs:
                dispatcher = NotificationDispatcher()
                for job in top_jobs:
                    await dispatcher.dispatch_job_alert(job.to_dict())
    except Exception as e:
        logger.error(f"Error during scheduled daily digest: {e}")


async def scheduled_weekly_digest_task():
    logger.info("Executing scheduled weekly job search & pipeline digest at 10:00 IST on Sunday...")
    try:
        from app.core.database import async_session_factory
        from app.notifiers.weekly_digest import WeeklyDigestNotifier

        async with async_session_factory() as session:
            notifier = WeeklyDigestNotifier()
            await notifier.dispatch_digest(session, days=7)
    except Exception as e:
        logger.error(f"Error during scheduled weekly digest: {e}")


async def scheduled_email_monitor_task():
    has_creds = bool((settings.GMAIL_USER and settings.GMAIL_APP_PASSWORD) or (settings.OUTLOOK_USER and settings.OUTLOOK_APP_PASSWORD))
    if not settings.EMAIL_MONITOR_ENABLED and not has_creds:
        return
    logger.info("Executing scheduled email inbox scan for hiring correspondence...")
    try:
        from app.email_monitor.inbox_scanner import InboxScanner
        scanner = InboxScanner()
        await scanner.scan_all_accounts()
    except Exception as e:
        logger.error(f"Error during scheduled email monitor scan: {e}")


async def scheduled_linkedin_post_task():
    """Generates and dispatches daily LinkedIn engineering post draft at 09:00 IST."""
    logger.info("Executing scheduled daily LinkedIn post draft task at 09:00 IST...")
    try:
        from datetime import datetime, timezone, timedelta
        from sqlalchemy import select
        from app.core.database import async_session_factory
        from app.core.models import LinkedInPost
        from app.intelligence.linkedin_post_generator import LinkedInPostGenerator
        from app.notifiers.telegram import TelegramNotifier

        ist = timezone(timedelta(hours=5, minutes=30))
        today_str = datetime.now(ist).strftime("%Y-%m-%d")

        async with async_session_factory() as session:
            res = await session.execute(select(LinkedInPost).where(LinkedInPost.post_date == today_str))
            existing = res.scalar_one_or_none()
            if existing and existing.notified_telegram:
                logger.info(f"Daily LinkedIn post for {today_str} already exists and notified.")
                return

            if not existing:
                gen = LinkedInPostGenerator()
                draft = await gen.generate_daily_post()
                existing = LinkedInPost(
                    post_date=today_str,
                    theme=draft["theme"],
                    hook=draft["hook"],
                    content=draft["content"],
                    hashtags=draft["hashtags"],
                    call_to_action=draft["call_to_action"],
                    posted=False,
                    notified_telegram=False,
                )
                session.add(existing)
                await session.commit()
                await session.refresh(existing)

            # Send to Telegram
            telegram = TelegramNotifier()
            if telegram.is_configured and not existing.notified_telegram:
                msg = (
                    f"📱 *DAILY LINKEDIN POST DRAFT*\n"
                    f"📅 *Date:* {today_str} • *Theme:* {existing.theme}\n\n"
                    f"💡 *Hook:*\n_{existing.hook}_\n\n"
                    f"📝 *Full Post Body (Copy & Share):*\n"
                    f"```{existing.content}```\n\n"
                    f"🏷️ *Hashtags:* {existing.hashtags}\n\n"
                    f"👉 [Open LinkedIn to Post](https://www.linkedin.com/feed/)"
                )
                sent = await telegram.send_message(msg, parse_mode="Markdown")
                if sent:
                    existing.notified_telegram = True
                    await session.commit()
                    logger.info(f"Dispatched daily LinkedIn post to Telegram for {today_str}.")
    except Exception as e:
        logger.error(f"Error during scheduled LinkedIn post draft: {e}")


def get_scheduler_status() -> Dict[str, Any]:
    job = scheduler.get_job("job_discovery_cycle") if scheduler.running else None
    next_run = job.next_run_time.isoformat() if job and job.next_run_time else None
    cleanup_job = scheduler.get_job("daily_data_cleanup") if scheduler.running else None
    next_cleanup = cleanup_job.next_run_time.isoformat() if cleanup_job and cleanup_job.next_run_time else None
    digest_job = scheduler.get_job("daily_digest") if scheduler.running else None
    next_digest = digest_job.next_run_time.isoformat() if digest_job and digest_job.next_run_time else None
    email_job = scheduler.get_job("email_monitor_cycle") if scheduler.running else None
    next_email = email_job.next_run_time.isoformat() if email_job and email_job.next_run_time else None
    linkedin_job = scheduler.get_job("daily_linkedin_post") if scheduler.running else None
    next_linkedin = linkedin_job.next_run_time.isoformat() if linkedin_job and linkedin_job.next_run_time else None

    return {
        "running": scheduler.running,
        "interval_minutes": settings.SCRAPE_INTERVAL_MINUTES,
        "next_scrape_at": next_run,
        "next_cleanup_at": next_cleanup,
        "next_digest_at": next_digest,
        "next_email_scan_at": next_email,
        "next_linkedin_post_at": next_linkedin,
        "retention_days": settings.DATA_RETENTION_DAYS,
    }


def start_scheduler():
    if not settings.SCHEDULER_ENABLED:
        logger.info("Scheduler is disabled in configuration.")
        return

    interval_mins = max(5, settings.SCRAPE_INTERVAL_MINUTES)
    first_run = utcnow() + timedelta(seconds=15)
    scheduler.add_job(
        scheduled_scrape_task,
        "interval",
        minutes=interval_mins,
        id="job_discovery_cycle",
        next_run_time=first_run,
        replace_existing=True,
    )

    if settings.AUTO_CLEANUP_ENABLED:
        # Schedule cleanup at 03:00 IST
        scheduler.add_job(
            scheduled_cleanup_task,
            "cron",
            hour=3,
            minute=0,
            timezone="Asia/Kolkata",
            id="daily_data_cleanup",
            replace_existing=True,
        )

    # Schedule daily digest at 08:00 IST
    scheduler.add_job(
        scheduled_digest_task,
        "cron",
        hour=8,
        minute=0,
        timezone="Asia/Kolkata",
        id="daily_digest",
        replace_existing=True,
    )

    # Schedule daily LinkedIn post draft at 09:00 IST
    scheduler.add_job(
        scheduled_linkedin_post_task,
        "cron",
        hour=9,
        minute=0,
        timezone="Asia/Kolkata",
        id="daily_linkedin_post",
        replace_existing=True,
    )

    # Schedule weekly executive digest every Sunday at 10:00 IST
    scheduler.add_job(
        scheduled_weekly_digest_task,
        "cron",
        day_of_week="sun",
        hour=10,
        minute=0,
        timezone="Asia/Kolkata",
        id="weekly_pipeline_digest",
        replace_existing=True,
    )

    # Schedule email monitor (Gmail & Outlook)
    if settings.EMAIL_MONITOR_ENABLED or (settings.GMAIL_USER and settings.GMAIL_APP_PASSWORD) or (settings.OUTLOOK_USER and settings.OUTLOOK_APP_PASSWORD):
        email_interval = max(5, settings.EMAIL_CHECK_INTERVAL_MINUTES)
        email_first_run = utcnow() + timedelta(seconds=45)
        scheduler.add_job(
            scheduled_email_monitor_task,
            "interval",
            minutes=email_interval,
            id="email_monitor_cycle",
            next_run_time=email_first_run,
            replace_existing=True,
        )

    scheduler.start()
    logger.info(
        f"Scheduler started. Discovery running every {interval_mins} mins (initial run at {first_run.isoformat()})."
    )

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped.")
