import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, List

from sqlalchemy import select
from app.config import settings
from app.core.database import async_session_factory
from app.core.models import JobPosting, TailoredApplication
from app.core.trace import log_audit_event
from app.intelligence.stair_matcher import StairMatcher
from app.intelligence.resume_tailor import ResumeTailor
from app.intelligence.outreach_generator import OutreachGenerator
from app.intelligence.pdf_compiler import PDFCompiler
from app.notifiers.dispatcher import NotificationDispatcher
from app.scrapers.direct_ats import DirectATSScraper
from app.scrapers.remote_boards import RemoteBoardsScraper
from app.scrapers.search_dorks import SearchDorksScraper
from app.scrapers.jobspy_scraper import JobSpyScraper

logger = logging.getLogger("personal_job_agent.engine")

class ScraperEngine:
    """
    Central Scraper & Automation Engine.
    Orchestrates job discovery, STAIR evaluation, database deduplication,
    real-time notification dispatch, and automated resume tailoring.
    """

    def __init__(self):
        self.matcher = StairMatcher()
        self.tailor = ResumeTailor()
        self.outreach = OutreachGenerator()
        self.pdf_compiler = PDFCompiler()
        self.notifier = NotificationDispatcher()

        # Initialize scrapers
        self.scrapers = [
            DirectATSScraper(),
            RemoteBoardsScraper(),
            SearchDorksScraper(),
            JobSpyScraper()
        ]

    async def run_discovery_cycle(self, scraper_filter: str = "all") -> Dict[str, Any]:
        """Runs discovery, matching, notification, and auto-tailoring."""
        start_time = datetime.utcnow()
        logger.info(f"Starting job discovery cycle (filter: {scraper_filter})...")

        raw_jobs = []
        active_scrapers = self.scrapers
        if scraper_filter == "ats":
            active_scrapers = [s for s in self.scrapers if isinstance(s, DirectATSScraper)]
        elif scraper_filter == "remote":
            active_scrapers = [s for s in self.scrapers if isinstance(s, RemoteBoardsScraper)]
        elif scraper_filter == "dorks":
            active_scrapers = [s for s in self.scrapers if isinstance(s, SearchDorksScraper)]

        for scraper in active_scrapers:
            try:
                res = await scraper.scrape()
                raw_jobs.extend(res)
            except Exception as e:
                logger.error(f"Scraper {scraper.name} failed: {e}")

        total_scraped = len(raw_jobs)
        new_jobs_count = 0
        high_match_count = 0
        notified_count = 0
        high_match_items = []

        # Phase 1: Ingest, deduplicate, evaluate STAIR score, and commit immediately
        async with async_session_factory() as session:
            for item in raw_jobs:
                url = item.get("url")
                if not url:
                    continue

                # Check deduplication
                existing = await session.execute(select(JobPosting.id).where(JobPosting.url == url))
                if existing.scalar_one_or_none() is not None:
                    continue # Already processed

                # STAIR Match Evaluation
                eval_res = self.matcher.evaluate_match(
                    title=item.get("title", ""),
                    company=item.get("company", ""),
                    location=item.get("location", ""),
                    description=item.get("description", "")
                )

                score = eval_res["score"]
                tier = eval_res["tier"]
                role_cat = eval_res["role_category"]

                job = JobPosting(
                    title=item.get("title", "")[:250],
                    company=item.get("company", "")[:250],
                    location=item.get("location", "Remote")[:250],
                    remote_status=item.get("remote_status", "Remote")[:50],
                    role_category=role_cat[:100],
                    url=url[:510],
                    source_platform=item.get("source_platform", "Web")[:100],
                    description=item.get("description", ""),
                    posted_date=item.get("posted_date", ""),
                    discovered_at=datetime.utcnow(),
                    match_score=score,
                    match_tier=tier,
                    match_reason=json.dumps(eval_res),
                    status="new",
                    notified=False
                )
                session.add(job)
                await session.flush() # Populate job.id
                new_jobs_count += 1

                if score >= settings.MIN_MATCH_SCORE_NOTIFY:
                    high_match_count += 1
                    high_match_items.append({
                        "job_id": job.id,
                        "job_dict": job.to_dict(),
                        "eval_res": eval_res,
                        "title": job.title,
                        "company": job.company,
                        "url": job.url,
                        "description": job.description
                    })

            await session.commit()

        # Phase 2: Dispatch notifications and tailor resumes WITHOUT holding open DB locks
        # Prioritize highest match scores first and throttle to top 5 per cycle to prevent LLM rate limits (429)
        high_match_items.sort(key=lambda x: x["eval_res"].get("score", 0.0), reverse=True)
        items_to_process = high_match_items[:5]

        for hm in items_to_process:
            alert_payload = hm["job_dict"]
            alert_payload["matched_skills"] = hm["eval_res"].get("matched_skills", [])

            # 1. Fire Real-time Notification
            notified = await self.notifier.dispatch_job_alert(alert_payload)
            if notified:
                try:
                    async with async_session_factory() as session:
                        j = await session.get(JobPosting, hm["job_id"])
                        if j:
                            j.notified = True
                            j.notified_at = datetime.utcnow()
                            await session.commit()
                            notified_count += 1
                except Exception as ne:
                    logger.error(f"Failed to update notification state for job {hm['job_id']}: {ne}")

            # 2. Automated Resume Tailoring & Outreach Draft (LLM call runs outside DB transaction)
            if settings.AUTO_TAILOR_HIGH_MATCH:
                try:
                    tailor_res = await self.tailor.tailor_resume(
                        job_title=hm["title"],
                        company=hm["company"],
                        description=hm["description"],
                        matched_skills=hm["eval_res"].get("matched_skills", [])
                    )

                    pdf_res = self.pdf_compiler.compile_resume(
                        job_id=hm["job_id"],
                        company_slug=hm["company"],
                        role_title=hm["title"],
                        latex_content=tailor_res["tailored_tex"]
                    )

                    outreach_res = self.outreach.generate_outreach(
                        job_title=hm["title"],
                        company=hm["company"],
                        job_url=hm["url"],
                        matched_skills=hm["eval_res"].get("matched_skills", [])
                    )

                    async with async_session_factory() as session:
                        app_record = TailoredApplication(
                            job_id=hm["job_id"],
                            tailored_resume_tex=tailor_res["tailored_tex"],
                            tailored_resume_md=tailor_res["tailored_md"],
                            pdf_path=pdf_res.get("pdf_path", ""),
                            cold_email_hr=outreach_res["hr_email"]["body"],
                            cold_email_hiring_manager=outreach_res["hiring_manager_email"]["body"],
                            linkedin_4mm=json.dumps(outreach_res["linkedin_4mm"]),
                            slop_score=tailor_res["slop_score"]
                        )
                        session.add(app_record)
                        j = await session.get(JobPosting, hm["job_id"])
                        if j:
                            j.status = "tailored"
                        await session.commit()
                except Exception as tailor_e:
                    logger.error(f"Auto-tailor failed for job {hm['job_id']}: {tailor_e}")

            # Respectful pacing between external LLM calls
            await asyncio.sleep(2.0)

        duration = (datetime.utcnow() - start_time).total_seconds()
        summary = {
            "total_scraped": total_scraped,
            "new_jobs": new_jobs_count,
            "high_match_jobs": high_match_count,
            "notified_count": notified_count,
            "duration_seconds": round(duration, 2)
        }

        await log_audit_event("scraper_cycle_complete", summary, "success")
        logger.info(f"Cycle completed: {summary}")
        return summary

