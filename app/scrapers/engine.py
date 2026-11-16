import asyncio
from datetime import timedelta
import hashlib
import json
import logging
from typing import Any, Dict
from sqlalchemy import func, select
from app.config import settings
from app.core.clock import utcnow
from app.core.database import async_session_factory
from app.core.fingerprint import compute_fingerprint
from app.core.models import JobPosting, SeenJob, TailoredApplication
from app.core.system import get_process_memory_mb
from app.core.trace import log_audit_event
from app.intelligence.stair_matcher import StairMatcher
from app.intelligence.resume_tailor import ResumeTailor
from app.intelligence.outreach_generator import OutreachGenerator
from app.intelligence.pdf_compiler import PDFCompiler
from app.intelligence.liveness import posting_is_closed
from app.notifiers.dispatcher import NotificationDispatcher
from app.scrapers.base import parse_posted_date
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

    _shared_cycle_lock: asyncio.Lock = asyncio.Lock()

    def __init__(self, cycle_lock: Any = None):
        self.matcher = StairMatcher()
        self.tailor = ResumeTailor()
        self.outreach = OutreachGenerator()
        self.pdf_compiler = PDFCompiler()
        self.notifier = NotificationDispatcher()
        self._cycle_lock = cycle_lock or ScraperEngine._shared_cycle_lock

        # Initialize scrapers
        self.scrapers = [
            DirectATSScraper(),
            RemoteBoardsScraper(),
            SearchDorksScraper(),
            JobSpyScraper()
        ]

    async def run_discovery_cycle(self, scraper_filter: str = "all") -> Dict[str, Any]:
        """Runs discovery, matching, notification, and auto-tailoring."""
        if self._cycle_lock.locked():
            logger.warning("Discovery cycle already in progress; skipping concurrent request.")
            return {
                "status": "busy",
                "message": "Discovery cycle already in progress",
                "total_scraped": 0,
                "new_jobs": 0,
                "high_match_jobs": 0,
                "notified_count": 0,
            }

        async with self._cycle_lock:
            start_time = utcnow()
            logger.info(f"Starting job discovery cycle (filter: {scraper_filter})...")

            active_scrapers = self.scrapers
            if scraper_filter == "ats":
                active_scrapers = [s for s in self.scrapers if isinstance(s, DirectATSScraper)]
            elif scraper_filter == "remote":
                active_scrapers = [s for s in self.scrapers if isinstance(s, RemoteBoardsScraper)]
            elif scraper_filter == "dorks":
                active_scrapers = [s for s in self.scrapers if isinstance(s, SearchDorksScraper)]

            total_scraped = 0
            new_jobs_count = 0
            high_match_count = 0
            notified_count = 0

            batch_urls = set()
            batch_fingerprints = set()

            # Phase 1: Ingest scraper-by-scraper, deduplicate, evaluate STAIR score, and commit immediately
            for scraper in active_scrapers:
                try:
                    items = await scraper.scrape()
                except Exception as e:
                    logger.error(f"Scraper {scraper.name} failed: {e}")
                    continue

                if not items:
                    continue

                total_scraped += len(items)

                async with async_session_factory() as session:
                    for item in items:
                        url = item.get("url")
                        if not url or url in batch_urls:
                            continue

                        # Truncate descriptions to ~8,000 characters at ingest
                        raw_desc = item.get("description") or ""
                        if len(raw_desc) > 8000:
                            raw_desc = raw_desc[:8000]

                        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()

                        fp = compute_fingerprint(
                            company=item.get("company", ""),
                            title=item.get("title", ""),
                            location=item.get("location", "")
                        )
                        if fp in batch_fingerprints:
                            continue

                        now = utcnow()

                        # 1. Check seen_jobs table (persistent dedup memory that survives retention purges)
                        seen_stmt = select(SeenJob).where(
                            (SeenJob.url_hash == url_hash) | (SeenJob.fingerprint == fp)
                        )
                        matched_seen = (await session.execute(seen_stmt)).scalars().all()
                        if matched_seen:
                            for s in matched_seen:
                                s.last_seen_at = now
                            batch_urls.add(url)
                            batch_fingerprints.add(fp)
                            continue

                        # 2. Check jobs table (exact URL or exact fingerprint)
                        existing_job_res = await session.execute(
                            select(JobPosting.id).where(
                                (JobPosting.url == url) | (JobPosting.fingerprint == fp)
                            ).limit(1)
                        )
                        if existing_job_res.scalars().first() is not None:
                            batch_urls.add(url)
                            batch_fingerprints.add(fp)
                            continue

                        # Freshness Gate: Parse posted_date and verify age <= MAX_JOB_AGE_DAYS
                        raw_posted_date = item.get("posted_date")
                        parsed_posted_at = parse_posted_date(raw_posted_date)
                        freshness_cutoff = now - timedelta(days=settings.MAX_JOB_AGE_DAYS)

                        if parsed_posted_at is not None:
                            posted_at = parsed_posted_at
                            posted_date_unverified = False
                            if posted_at < freshness_cutoff:
                                logger.debug(
                                    f"Dropping stale job '{item.get('title')}' posted at {posted_at} (older than {settings.MAX_JOB_AGE_DAYS} days)"
                                )
                                continue
                        else:
                            posted_at = None
                            posted_date_unverified = True

                        # STAIR Match Evaluation
                        eval_res = self.matcher.evaluate_match(
                            title=item.get("title", ""),
                            company=item.get("company", ""),
                            location=item.get("location", ""),
                            description=raw_desc
                        )

                        score = eval_res["score"]
                        tier = eval_res["tier"]
                        role_cat = eval_res["role_category"]

                        job = JobPosting(
                            title=item.get("title", "")[:500],
                            company=item.get("company", "")[:250],
                            location=(item.get("location") or "Unknown")[:500],
                            remote_status=(item.get("remote_status") or "Unknown")[:100],
                            role_category=role_cat[:250],
                            fingerprint=fp,
                            url=url[:1000],
                            source_platform=item.get("source_platform", "Web")[:100],
                            description=raw_desc,
                            posted_date=str(item.get("posted_date", "") or "")[:100],
                            posted_at=posted_at,
                            posted_date_unverified=posted_date_unverified,
                            discovered_at=now,
                            match_score=score,
                            match_tier=tier[:100],
                            match_reason=json.dumps(eval_res),
                            status="new",
                            notified=False
                        )
                        session.add(job)
                        session.add(
                            SeenJob(
                                url_hash=url_hash,
                                fingerprint=fp,
                                first_seen_at=now,
                                last_seen_at=now,
                            )
                        )
                        batch_urls.add(url)
                        batch_fingerprints.add(fp)
                        new_jobs_count += 1

                        if score >= settings.MIN_MATCH_SCORE_NOTIFY:
                            high_match_count += 1

                    await session.commit()

            # Phase 2: Dispatch notifications and tailor resumes WITHOUT holding open DB locks
            # DB-backed queue: Pick up unnotified high-match jobs ordered by score descending.
            # This processes up to 5 per cycle to prevent LLM rate limits (429) without starving any backlog.
            pending_jobs = []
            now_phase2 = utcnow()
            notify_cutoff = now_phase2 - timedelta(days=settings.MAX_JOB_AGE_DAYS)
            effective_dt = func.coalesce(JobPosting.posted_at, JobPosting.discovered_at)
            async with async_session_factory() as session:
                stmt = (
                    select(JobPosting)
                    .where(
                        JobPosting.notified == False,
                        JobPosting.match_score >= settings.MIN_MATCH_SCORE_NOTIFY,
                        JobPosting.notify_attempts < settings.MAX_NOTIFY_ATTEMPTS,
                        (JobPosting.next_attempt_at.is_(None)) | (JobPosting.next_attempt_at <= now_phase2),
                        effective_dt >= notify_cutoff
                    )
                    .order_by(JobPosting.match_score.desc(), JobPosting.discovered_at.desc())
                    .limit(5)
                )
                res = await session.execute(stmt)
                for j in res.scalars().all():
                    eval_meta = {}
                    try:
                        if j.match_reason:
                            eval_meta = json.loads(j.match_reason)
                    except Exception:
                        pass
                    pending_jobs.append({
                        "job_id": j.id,
                        "job_dict": j.to_dict(),
                        "eval_res": eval_meta,
                        "title": j.title,
                        "company": j.company,
                        "url": j.url,
                        "description": j.description,
                        "notify_attempts": j.notify_attempts or 0,
                        "tailor_status": j.tailor_status or "pending",
                    })

            has_notifier = self.notifier.is_any_configured
            if not has_notifier:
                logger.info("No notification channels configured; skipping push alert dispatch this cycle.")

            for hm in pending_jobs:
                job_id = hm["job_id"]
                job_url = hm["url"]

                # Fast liveness pre-check: prune closed postings before alerting or tailoring
                if await posting_is_closed(job_url):
                    logger.info(
                        f"Skipping notification/tailoring for job {job_id} ({hm['title']} at {hm['company']}): "
                        f"posting is closed on ATS."
                    )
                    async with async_session_factory() as session:
                        j = await session.get(JobPosting, job_id)
                        if j:
                            j.status = "closed"
                            j.notified = True
                            j.last_error = "Posting closed on ATS (liveness check)"
                            await session.commit()
                    continue

                alert_payload = hm["job_dict"]
                alert_payload["matched_skills"] = hm["eval_res"].get("matched_skills", [])

                # 1. Fire Real-time Notification
                if has_notifier:
                    now_attempt = utcnow()
                    try:
                        notified = await self.notifier.dispatch_job_alert(alert_payload)
                    except Exception as notify_err:
                        logger.error(f"Failed to dispatch notification for job {job_id}: {notify_err}")
                        notified = False

                    async with async_session_factory() as session:
                        j = await session.get(JobPosting, job_id)
                        if j:
                            if notified:
                                j.notified = True
                                j.notified_at = now_attempt
                                j.last_error = None
                                notified_count += 1
                            else:
                                attempts = (j.notify_attempts or 0) + 1
                                j.notify_attempts = attempts
                                backoff_minutes = min(120, 5 * (2 ** (attempts - 1)))
                                j.next_attempt_at = now_attempt + timedelta(minutes=backoff_minutes)
                                j.last_error = "Notification failed across configured channels"[:500]
                                if attempts >= settings.MAX_NOTIFY_ATTEMPTS:
                                    logger.warning(
                                        f"Job {job_id} reached max notification attempts ({attempts}). Abandoning notification."
                                    )
                                    await log_audit_event(
                                        "notification_abandoned",
                                        {
                                            "job_id": job_id,
                                            "title": j.title,
                                            "attempts": attempts,
                                            "last_error": j.last_error
                                        },
                                        "warning"
                                    )
                            await session.commit()

                # 2. Automated Resume Tailoring & Outreach Draft (LLM call runs outside DB transaction)
                # Runs only when tailor_status == "pending", once per job
                if settings.AUTO_TAILOR_HIGH_MATCH and hm["tailor_status"] == "pending":
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
                                j.tailor_status = "done"
                            await session.commit()
                    except Exception as tailor_e:
                        logger.error(f"Auto-tailor failed for job {hm['job_id']}: {tailor_e}")
                        async with async_session_factory() as session:
                            j = await session.get(JobPosting, hm["job_id"])
                            if j:
                                j.tailor_status = "failed"
                            await session.commit()

                # Respectful pacing between external LLM calls
                await asyncio.sleep(2.0)

            duration = (utcnow() - start_time).total_seconds()
            memory_rss = get_process_memory_mb()
            summary = {
                "total_scraped": total_scraped,
                "new_jobs": new_jobs_count,
                "high_match_jobs": high_match_count,
                "notified_count": notified_count,
                "duration_seconds": round(duration, 2),
                "memory_rss_mb": memory_rss,
            }

            await log_audit_event("scraper_cycle_complete", summary, "success")
            logger.info(f"Cycle completed: {summary} (Memory RSS: {memory_rss} MB)")
            return summary

