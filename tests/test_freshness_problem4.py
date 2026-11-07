from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core import clock
from app.core.models import Base, JobPosting
from app.scrapers.base import parse_posted_date
from app.scrapers.engine import ScraperEngine


def test_parse_posted_date_various_formats():
    now = clock.utcnow()

    # None and empty
    assert parse_posted_date(None) is None
    assert parse_posted_date("") is None
    assert parse_posted_date("invalid gibberish date string") is None

    # Just posted / today / yesterday
    just_posted = parse_posted_date("just posted")
    assert just_posted is not None
    assert abs((now - just_posted).total_seconds()) < 60

    today = parse_posted_date("today")
    assert today is not None
    assert abs((now - today).total_seconds()) < 60

    yesterday = parse_posted_date("yesterday")
    assert yesterday is not None
    assert 23 * 3600 <= (now - yesterday).total_seconds() <= 25 * 3600

    # Relative days and hours
    two_days_ago = parse_posted_date("2 days ago")
    assert two_days_ago is not None
    assert 47 * 3600 <= (now - two_days_ago).total_seconds() <= 49 * 3600

    twelve_hrs_ago = parse_posted_date("12 hours ago")
    assert twelve_hrs_ago is not None
    assert 11 * 3600 <= (now - twelve_hrs_ago).total_seconds() <= 13 * 3600

    # Short forms: 3d ago, 2w ago, 5m ago
    three_d = parse_posted_date("3d ago")
    assert three_d is not None
    assert 71 * 3600 <= (now - three_d).total_seconds() <= 73 * 3600

    two_w = parse_posted_date("2w ago")
    assert two_w is not None
    assert 13 * 86400 <= (now - two_w).total_seconds() <= 15 * 86400

    # ISO strings
    iso_dt = parse_posted_date("2026-11-01T10:30:00Z")
    assert iso_dt is not None
    assert iso_dt == datetime(2026, 11, 1, 10, 30, 0, tzinfo=timezone.utc)

    # Epoch seconds and ms
    epoch_sec = parse_posted_date(1762000000)
    assert epoch_sec is not None
    assert epoch_sec.tzinfo is not None

    epoch_ms = parse_posted_date(1762000000000)
    assert epoch_ms is not None
    assert epoch_ms == epoch_sec


@pytest.mark.asyncio
async def test_freshness_gate_in_engine_discovery(tmp_path, monkeypatch):
    db_path = tmp_path / "test_freshness.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    test_engine = create_async_engine(db_url)
    test_session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Monkeypatch session factory in database and engine
    monkeypatch.setattr("app.scrapers.engine.async_session_factory", test_session_factory)

    engine = ScraperEngine()
    # Disable external notifiers
    monkeypatch.setattr(engine.notifier, "dispatch_job_alert", lambda *args, **kwargs: False)

    now = clock.utcnow()
    stale_date = (now - timedelta(days=10)).strftime("%Y-%m-%d")
    fresh_date = (now - timedelta(days=2)).strftime("%Y-%m-%d")

    dummy_jobs = [
        {
            "title": "Backend Python Developer",
            "company": "Stale Corp",
            "location": "Hyderabad, India",
            "url": "https://example.com/jobs/stale-1",
            "source_platform": "Direct ATS",
            "description": "Python, FastAPI, SQL backend engineer.",
            "posted_date": stale_date, # 10 days old -> should be dropped
        },
        {
            "title": "Senior Python Engineer",
            "company": "Fresh Corp",
            "location": "Hyderabad, India",
            "url": "https://example.com/jobs/fresh-1",
            "source_platform": "Direct ATS",
            "description": "Python, FastAPI, Docker, PostgreSQL engineer.",
            "posted_date": fresh_date, # 2 days old -> should be accepted
        },
        {
            "title": "Python Software Engineer",
            "company": "Unknown Date Corp",
            "location": "Bengaluru, India",
            "url": "https://example.com/jobs/unknown-date-1",
            "source_platform": "Direct ATS",
            "description": "Python backend services developer.",
            "posted_date": "", # Unknown date -> unverified date fallback
        },
    ]

    class MockScraper:
        async def scrape(self):
            return dummy_jobs

    engine.scrapers = [MockScraper()]

    # Run discovery cycle
    stats = await engine.run_discovery_cycle()
    assert stats["new_jobs"] == 2 # 1 stale was dropped before insertion

    # Verify database contents
    async with test_session_factory() as session:
        result = await session.execute(select(JobPosting).order_by(JobPosting.title))
        saved_jobs = result.scalars().all()
        assert len(saved_jobs) == 2

        # Stale Corp was NOT saved
        companies = [j.company for j in saved_jobs]
        assert "Stale Corp" not in companies
        assert "Fresh Corp" in companies
        assert "Unknown Date Corp" in companies

        fresh_job = next(j for j in saved_jobs if j.company == "Fresh Corp")
        assert fresh_job.posted_at is not None
        assert fresh_job.posted_date_unverified is False

        unknown_job = next(j for j in saved_jobs if j.company == "Unknown Date Corp")
        assert unknown_job.posted_at is None
        assert unknown_job.posted_date_unverified is True
        assert unknown_job.discovered_at is not None

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_freshness_gate_in_notify_queue(tmp_path):
    db_path = tmp_path / "test_notify_freshness.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    test_engine = create_async_engine(db_url)
    test_session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    now = clock.utcnow()
    stale_dt = now - timedelta(days=10)
    fresh_dt = now - timedelta(days=2)

    async with test_session_factory() as session:
        # Job 1: high match, but stale posted_at
        j1 = JobPosting(
            title="Dev 1",
            company="C1",
            location="Remote",
            url="https://c1.com/1",
            source_platform="Web",
            match_score=90.0,
            match_tier="Tier 1",
            notified=False,
            posted_at=stale_dt,
            discovered_at=now,
        )
        # Job 2: high match, fresh posted_at
        j2 = JobPosting(
            title="Dev 2",
            company="C2",
            location="Remote",
            url="https://c2.com/2",
            source_platform="Web",
            match_score=90.0,
            match_tier="Tier 1",
            notified=False,
            posted_at=fresh_dt,
            discovered_at=now,
        )
        # Job 3: high match, posted_at is None, but discovered_at is fresh
        j3 = JobPosting(
            title="Dev 3",
            company="C3",
            location="Remote",
            url="https://c3.com/3",
            source_platform="Web",
            match_score=85.0,
            match_tier="Tier 1",
            notified=False,
            posted_at=None,
            posted_date_unverified=True,
            discovered_at=fresh_dt,
        )
        # Job 4: high match, posted_at is None, discovered_at is stale
        j4 = JobPosting(
            title="Dev 4",
            company="C4",
            location="Remote",
            url="https://c4.com/4",
            source_platform="Web",
            match_score=85.0,
            match_tier="Tier 1",
            notified=False,
            posted_at=None,
            posted_date_unverified=True,
            discovered_at=stale_dt,
        )
        session.add_all([j1, j2, j3, j4])
        await session.commit()

        # Run Phase 2 notify query
        notify_cutoff = now - timedelta(days=settings.MAX_JOB_AGE_DAYS)
        effective_dt = func.coalesce(JobPosting.posted_at, JobPosting.discovered_at)

        stmt = (
            select(JobPosting)
            .where(
                JobPosting.match_score >= settings.MIN_MATCH_SCORE_NOTIFY,
                JobPosting.notified == False,
                effective_dt >= notify_cutoff,
            )
            .order_by(JobPosting.match_score.desc(), JobPosting.discovered_at.desc())
        )
        res = await session.execute(stmt)
        pending = res.scalars().all()

        assert len(pending) == 2
        selected_titles = [j.title for j in pending]
        assert "Dev 2" in selected_titles
        assert "Dev 3" in selected_titles
        assert "Dev 1" not in selected_titles
        assert "Dev 4" not in selected_titles

    await test_engine.dispose()
