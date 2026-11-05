import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import settings
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

def get_scheduler_status() -> Dict[str, Any]:
    job = scheduler.get_job("job_discovery_cycle") if scheduler.running else None
    next_run = job.next_run_time.isoformat() if job and job.next_run_time else None
    return {
        "running": scheduler.running,
        "interval_minutes": settings.SCRAPE_INTERVAL_MINUTES,
        "next_scrape_at": next_run
    }

def start_scheduler():
    if not settings.SCHEDULER_ENABLED:
        logger.info("Scheduler is disabled in configuration.")
        return

    interval_mins = max(5, settings.SCRAPE_INTERVAL_MINUTES)
    first_run = datetime.now(timezone.utc) + timedelta(seconds=15)
    scheduler.add_job(
        scheduled_scrape_task,
        "interval",
        minutes=interval_mins,
        id="job_discovery_cycle",
        next_run_time=first_run,
        replace_existing=True
    )
    scheduler.start()
    logger.info(f"Scheduler started. Discovery running every {interval_mins} mins (initial run at {first_run.isoformat()}).")

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped.")
