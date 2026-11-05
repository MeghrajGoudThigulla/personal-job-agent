import logging
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

def start_scheduler():
    if not settings.SCHEDULER_ENABLED:
        logger.info("Scheduler is disabled in configuration.")
        return

    interval_mins = max(5, settings.SCRAPE_INTERVAL_MINUTES)
    scheduler.add_job(
        scheduled_scrape_task,
        "interval",
        minutes=interval_mins,
        id="job_discovery_cycle",
        replace_existing=True
    )
    scheduler.start()
    logger.info(f"Scheduler started. Job discovery running every {interval_mins} minutes.")

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped.")
