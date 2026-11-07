import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.models import Base, JobPosting
from app.intelligence.stair_matcher import StairMatcher
from app.scrapers.engine import ScraperEngine


def test_evaluate_location_unknown_and_exclusions_and_india():
    matcher = StairMatcher()

    # 1. Unknown location without India mentions -> LOCATION_UNVERIFIED, score 0.0, eligible False
    eligible, score, cat, detail = matcher.evaluate_location(
        location="Unknown",
        description="We are looking for a Python FastAPI developer to build scalable microservices.",
        title="Software Engineer",
    )
    assert eligible is False
    assert score == 0.0
    assert cat == "LOCATION_UNVERIFIED"

    # Also test empty string or None location
    eligible_empty, score_empty, cat_empty, _ = matcher.evaluate_location(
        location="",
        description="Python backend developer wanted.",
        title="Python Dev",
    )
    assert eligible_empty is False
    assert score_empty == 0.0
    assert cat_empty == "LOCATION_UNVERIFIED"

    # 2. Unknown location with US only exclusion -> rejected as Excluded (Restricted Region)
    eligible_us, score_us, cat_us, _ = matcher.evaluate_location(
        location="Unknown",
        description="Senior Python developer. Must reside in US only. Authorized to work in the United States.",
        title="Software Engineer",
    )
    assert eligible_us is False
    assert score_us == 0.0
    assert "Restricted Region" in cat_us

    # 3. Unknown location with explicit "Remote, India" -> accepted as Remote (India, from posting)
    eligible_ind, score_ind, cat_ind, _ = matcher.evaluate_location(
        location="Unknown",
        description="We are hiring anywhere across India! Work from India remote position for Python developers.",
        title="Python Developer",
    )
    assert eligible_ind is True
    assert score_ind == 25.0
    assert cat_ind == "Remote (India, from posting)"

    # Also test IST timezone mentioned in description
    eligible_ist, score_ist, cat_ist, _ = matcher.evaluate_location(
        location="Unknown",
        description="Looking for Python engineers working in IST timezone.",
        title="Python Developer",
    )
    assert eligible_ist is True
    assert score_ist == 25.0
    assert cat_ist == "Remote (India, from posting)"


def test_evaluate_match_produces_excluded_location_unverified_tier():
    matcher = StairMatcher()

    # High stack match (Python + FastAPI + Postgres + Docker), but unknown location
    eval_res = matcher.evaluate_match(
        title="Software Engineer - Backend",
        company="GlobalTech",
        location="Unknown",
        description="We build Python and FastAPI backend services with Postgres, Docker, and Redis.",
    )
    assert eval_res["score"] == 0.0
    assert eval_res["tier"] == "Excluded (Location Unverified)"
    assert eval_res["location_category"] == "LOCATION_UNVERIFIED"


@pytest.mark.asyncio
async def test_location_unverified_saved_as_new_but_never_enters_notify_queue(tmp_path, monkeypatch):
    db_path = tmp_path / "test_unverified_queue.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    test_engine = create_async_engine(db_url)
    test_session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr("app.scrapers.engine.async_session_factory", test_session_factory)
    monkeypatch.setattr("app.config.settings.AUTO_TAILOR_HIGH_MATCH", False)

    engine = ScraperEngine()
    monkeypatch.setattr(
        "app.notifiers.dispatcher.NotificationDispatcher.is_any_configured",
        property(lambda self: True),
    )

    notified_jobs = []

    async def mock_dispatch(payload):
        notified_jobs.append(payload["title"])
        return True

    monkeypatch.setattr(engine.notifier, "dispatch_job_alert", mock_dispatch)

    raw_jobs = [
        # Job 1: Dork result with Unknown location and no India keywords
        {
            "title": "Software Engineer - Python",
            "company": "Mystery Corp",
            "location": "Unknown",
            "remote_status": "Unknown",
            "url": "https://mystery.com/jobs/1",
            "source_platform": "SearchDork",
            "description": "Python, FastAPI, SQL backend services developer.",
            "posted_date": "yesterday",
        },
        # Job 2: Dork result with explicit India eligibility in description
        {
            "title": "Software Engineer - Python India",
            "company": "India Corp",
            "location": "Unknown",
            "remote_status": "Unknown",
            "url": "https://india.com/jobs/2",
            "source_platform": "SearchDork",
            "description": "Python, FastAPI, Docker engineer. Hiring in India (work from India remote).",
            "posted_date": "yesterday",
        },
    ]

    class MockScraper:
        async def scrape(self):
            return raw_jobs

    engine.scrapers = [MockScraper()]
    await engine.run_discovery_cycle()

    # Verify Job 1 was saved as new with tier 'Excluded (Location Unverified)' and score 0.0
    async with test_session_factory() as session:
        j1 = (await session.execute(select(JobPosting).where(JobPosting.company == "Mystery Corp"))).scalar_one()
        assert j1.status == "new"
        assert j1.match_tier == "Excluded (Location Unverified)"
        assert j1.match_score == 0.0
        assert j1.notified is False
        assert j1.notify_attempts == 0

        # Job 2 was accepted with high score and notified
        j2 = (await session.execute(select(JobPosting).where(JobPosting.company == "India Corp"))).scalar_one()
        assert j2.match_score >= settings.MIN_MATCH_SCORE_NOTIFY
        assert j2.notified is True

    # Crucial: Mystery Corp was NEVER notified
    assert "Software Engineer - Python" not in notified_jobs
    assert "Software Engineer - Python India" in notified_jobs

    await test_engine.dispose()
