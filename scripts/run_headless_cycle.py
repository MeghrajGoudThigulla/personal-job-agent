#!/usr/bin/env python3
"""
Headless Automation Runner for GitHub Actions / Cron / 24-7 Background Jobs.

Executes autonomous discovery cycles without running a web server:
1. Runs database initialization / migrations.
2. Discovers, deduplicates, and scores job postings with STAIR.
3. Automatically tails, attaches, and dispatches resumes & cover letters to Telegram.
4. Generates and dispatches daily LinkedIn engineering post draft at ~09:00 AM IST.
5. Monitors email inboxes for recruiter correspondence (if credentials provided).
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone, timedelta
import logging
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import settings
from app.core.database import init_db, async_session_factory
from app.core.models import JobPosting, LinkedInPost
from app.scrapers.engine import ScraperEngine
from app.intelligence.linkedin_post_generator import LinkedInPostGenerator
from app.notifiers.telegram import TelegramNotifier
from sqlalchemy import select, func

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("personal_job_agent.headless_runner")
IST = timezone(timedelta(hours=5, minutes=30))


async def run_discovery_step() -> dict:
    """Executes the complete job discovery, matching, and notification cycle with a 3-minute safety timeout."""
    logger.info("=== STEP 1: Starting autonomous job discovery cycle ===")
    engine = ScraperEngine()
    try:
        result = await asyncio.wait_for(engine.run_discovery_cycle(), timeout=180.0)
        logger.info(f"Discovery cycle finished: {result}")
        return result
    except asyncio.TimeoutError:
        logger.warning("Discovery cycle reached 180s timeout limit; gracefully proceeding with current results.")
        return {"status": "timeout", "message": "Circuit breaker hit at 180s"}


async def run_linkedin_step(force: bool = False) -> None:
    """Generates today's LinkedIn engineering post draft if not already generated."""
    now_ist = datetime.now(IST)
    today_str = now_ist.strftime("%Y-%m-%d")
    logger.info(f"=== STEP 2: Checking Daily LinkedIn Post for {today_str} ===")

    async with async_session_factory() as session:
        query = select(LinkedInPost).where(LinkedInPost.post_date == today_str)
        res = await session.execute(query)
        existing = res.scalar_one_or_none()

        if existing and not force:
            logger.info(f"LinkedIn post for {today_str} already generated (ID: {existing.id}, Posted: {existing.posted}). Skipping.")
            return

        # Check if within morning window (08:00 - 12:00 IST) or force
        current_hour_ist = now_ist.hour
        is_morning = 8 <= current_hour_ist <= 12

        if not is_morning and not force:
            logger.info(f"Current IST hour is {current_hour_ist}:00. LinkedIn posts are scheduled for 09:00 IST. Skipping.")
            return

        logger.info(f"Generating authentic technical LinkedIn draft for {today_str}...")
        generator = LinkedInPostGenerator()
        draft = await generator.generate_daily_post(target_date=now_ist)

        if existing:
            existing.theme = draft["theme"]
            existing.hook = draft["hook"]
            existing.content = draft["content"]
            existing.hashtags = draft["hashtags"]
            existing.call_to_action = draft["call_to_action"]
            post = existing
        else:
            post = LinkedInPost(
                post_date=today_str,
                theme=draft["theme"],
                hook=draft["hook"],
                content=draft["content"],
                hashtags=draft["hashtags"],
                call_to_action=draft["call_to_action"],
                posted=False,
                notified_telegram=False,
            )
            session.add(post)

        await session.commit()
        await session.refresh(post)

        # Dispatch to Telegram
        telegram = TelegramNotifier()
        if telegram.is_configured:
            msg = (
                f"📱 *DAILY LINKEDIN POST DRAFT*\n"
                f"📅 *Date:* {today_str} • *Theme:* {post.theme}\n\n"
                f"💡 *Hook:*\n_{post.hook}_\n\n"
                f"📝 *Full Post Body (Copy & Share):*\n"
                f"```{post.content}```\n\n"
                f"🏷️ *Hashtags:* {post.hashtags}\n\n"
                f"👉 [Open LinkedIn to Post](https://www.linkedin.com/feed/)"
            )
            sent = await telegram.send_message(msg, parse_mode="Markdown")
            if sent:
                post.notified_telegram = True
                await session.commit()
                logger.info(f"Successfully dispatched LinkedIn draft to Telegram for {today_str}!")
        else:
            logger.warning("Telegram is not configured; post saved in database only.")


async def run_email_step() -> None:
    """Scans configured inboxes for recruiter correspondence."""
    has_creds = bool(
        (settings.GMAIL_USER and settings.GMAIL_APP_PASSWORD)
        or (settings.OUTLOOK_USER and settings.OUTLOOK_APP_PASSWORD)
    )
    if not settings.EMAIL_MONITOR_ENABLED and not has_creds:
        logger.info("=== STEP 3: Email monitor credentials not configured. Skipping. ===")
        return

    logger.info("=== STEP 3: Executing scheduled email monitor scan ===")
    try:
        from app.email_monitor.inbox_scanner import InboxScanner
        scanner = InboxScanner()
        results = await scanner.scan_all_accounts()
        logger.info(f"Email scan finished: {len(results.get('emails', []))} hiring emails found.")
    except Exception as e:
        logger.error(f"Error during email monitor step: {e}")


async def print_stats_summary() -> None:
    """Prints a clean summary of current pipeline state."""
    async with async_session_factory() as session:
        total = await session.scalar(select(func.count(JobPosting.id))) or 0
        high = await session.scalar(
            select(func.count(JobPosting.id)).where(JobPosting.match_score >= settings.MIN_MATCH_SCORE_NOTIFY)
        ) or 0
        tailored = await session.scalar(
            select(func.count(JobPosting.id)).where(JobPosting.status == "tailored")
        ) or 0
        applied = await session.scalar(
            select(func.count(JobPosting.id)).where(JobPosting.status.in_(["applied", "interviewing"]))
        ) or 0

        logger.info("================ PIPELINE METRICS ================")
        logger.info(f"  Total Tracked Jobs:      {total}")
        logger.info(f"  High Match Jobs (>=70%): {high}")
        logger.info(f"  Tailored Applications:   {tailored}")
        logger.info(f"  Active Pipeline Jobs:    {applied}")
        logger.info("==================================================")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Personal Job Agent Headless Runner")
    parser.add_argument("--scrape-only", action="store_true", help="Only run job discovery and matching")
    parser.add_argument("--linkedin-only", action="store_true", help="Only run LinkedIn post generator")
    parser.add_argument("--email-only", action="store_true", help="Only scan email inboxes")
    parser.add_argument("--force-linkedin", action="store_true", help="Force generate LinkedIn post regardless of hour")
    args = parser.parse_args()

    logger.info("Initializing database and models...")
    await init_db()
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger("personal_job_agent").setLevel(logging.INFO)
    logger.info("Database and migrations initialized.")

    if args.linkedin_only:
        await run_linkedin_step(force=True)
    elif args.email_only:
        await run_email_step()
    elif args.scrape_only:
        await run_discovery_step()
    else:
        # Full cycle: Scrape -> LinkedIn (if morning/force) -> Email
        await run_discovery_step()
        await run_linkedin_step(force=args.force_linkedin)
        await run_email_step()

    await print_stats_summary()
    logger.info("Headless execution cycle completed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
