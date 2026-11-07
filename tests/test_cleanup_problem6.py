from datetime import timedelta
from pathlib import Path
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core import clock
from app.core.cleanup import is_safe_resume_path, purge_old_records
from app.core.fingerprint import compute_fingerprint
from app.core.models import AuditLog, Base, JobPosting, SeenJob
from app.scrapers.engine import ScraperEngine


def test_is_safe_resume_path(tmp_path, monkeypatch):
    resumes_dir = tmp_path / "tailored_resumes"
    resumes_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("app.core.cleanup.Path", lambda p: (resumes_dir if p == "data/tailored_resumes" else Path(p)))

    # Valid file inside resumes dir
    valid_file = resumes_dir / "valid_resume.pdf"
    valid_file.write_text("dummy pdf content")
    assert is_safe_resume_path(str(valid_file)) is True

    # Dangerous file outside resumes dir
    outside_file = tmp_path / "system_file.txt"
    outside_file.write_text("do not delete")
    assert is_safe_resume_path(str(outside_file)) is False

    # Path traversal attack string
    traversal_path = str(resumes_dir / ".." / "system_file.txt")
    assert is_safe_resume_path(traversal_path) is False

    # Non-existent file
    assert is_safe_resume_path(str(resumes_dir / "ghost.pdf")) is False


@pytest.mark.asyncio
async def test_purged_job_not_reinserted_or_renotified(tmp_path, monkeypatch):
    db_path = tmp_path / "test_seen_purge.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    test_engine = create_async_engine(db_url)
    test_session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr("app.core.cleanup.async_session_factory", test_session_factory)
    monkeypatch.setattr("app.scrapers.engine.async_session_factory", test_session_factory)
    monkeypatch.setattr("app.config.settings.AUTO_TAILOR_HIGH_MATCH", False)

    engine = ScraperEngine()
    async def mock_dispatch(*args, **kwargs):
        return False
    monkeypatch.setattr(engine.notifier, "dispatch_job_alert", mock_dispatch)

    # 1. Scrape a high-match job today
    raw_job = {
        "title": "Backend Python Developer",
        "company": "TechStart Inc",
        "location": "Hyderabad, India",
        "url": "https://techstart.io/jobs/backend-1",
        "source_platform": "Direct ATS",
        "description": "Python, FastAPI, SQL, PostgreSQL backend developer.",
        "posted_date": "yesterday",
    }

    class MockScraper:
        async def scrape(self):
            return [raw_job]

    engine.scrapers = [MockScraper()]
    stats1 = await engine.run_discovery_cycle()
    assert stats1["new_jobs"] == 1

    # Verify both jobs table and seen_jobs table have the job
    async with test_session_factory() as session:
        job = (await session.execute(select(JobPosting))).scalar_one()
        assert job is not None
        seen = (await session.execute(select(SeenJob))).scalar_one()
        assert seen is not None
        assert seen.fingerprint == job.fingerprint

        # Age the job to 75 days ago (older than 60-day retention)
        now = clock.utcnow()
        old_date = now - timedelta(days=75)
        job.discovered_at = old_date
        await session.commit()

    # 2. Run retention purge (should purge JobPosting, but preserve SeenJob)
    purge_summary = await purge_old_records(retention_days=60)
    assert purge_summary["deleted_jobs"] == 1

    async with test_session_factory() as session:
        jobs_in_db = (await session.execute(select(JobPosting))).scalars().all()
        assert len(jobs_in_db) == 0 # Job was purged from jobs table

        seen_in_db = (await session.execute(select(SeenJob))).scalars().all()
        assert len(seen_in_db) == 1 # Seen history was preserved!

    # 3. Scrape again with the same job
    stats2 = await engine.run_discovery_cycle()
    # It must NOT be re-inserted or re-notified!
    assert stats2["new_jobs"] == 0

    async with test_session_factory() as session:
        jobs_after_rescrape = (await session.execute(select(JobPosting))).scalars().all()
        assert len(jobs_after_rescrape) == 0 # Still 0, not re-inserted!

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_chunked_purge_and_seen_retention(tmp_path, monkeypatch):
    db_path = tmp_path / "test_chunked_purge.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    test_engine = create_async_engine(db_url)
    test_session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr("app.core.cleanup.async_session_factory", test_session_factory)

    # Insert 1050 old jobs (exceeding chunk size 500)
    now = clock.utcnow()
    old_time = now - timedelta(days=70)
    ancient_time = now - timedelta(days=400) # older than 365 days

    async with test_session_factory() as session:
        jobs = []
        seen = []
        logs = []
        for i in range(1050):
            fp = compute_fingerprint(f"Company {i}", f"Role {i}", "Hyderabad")
            url = f"https://example.com/job/{i}"
            jobs.append(
                JobPosting(
                    title=f"Role {i}",
                    company=f"Company {i}",
                    location="Hyderabad",
                    url=url,
                    source_platform="Web",
                    fingerprint=fp,
                    discovered_at=old_time,
                    status="new",
                )
            )
            # Some seen_jobs are ancient (>365d), some are recent (<365d)
            seen_time = ancient_time if i < 200 else old_time
            seen.append(
                SeenJob(
                    url_hash=f"hash_{i}",
                    fingerprint=fp,
                    first_seen_at=seen_time,
                    last_seen_at=seen_time,
                )
            )
            logs.append(
                AuditLog(
                    timestamp=old_time,
                    action="scraper_cycle_complete",
                    details='{"test": true}',
                    status="success",
                )
            )
        session.add_all(jobs)
        session.add_all(seen)
        session.add_all(logs)
        await session.commit()

    # Run purge
    summary = await purge_old_records(retention_days=60)
    assert summary["deleted_jobs"] == 1050
    assert summary["deleted_audit_logs"] == 1050
    assert summary["deleted_seen_jobs"] == 200 # 200 ancient seen_jobs deleted, 850 preserved

    async with test_session_factory() as session:
        rem_jobs = (await session.execute(select(JobPosting))).scalars().all()
        assert len(rem_jobs) == 0

        rem_seen = (await session.execute(select(SeenJob))).scalars().all()
        assert len(rem_seen) == 850

    await test_engine.dispose()
