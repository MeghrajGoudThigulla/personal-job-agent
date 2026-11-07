import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.fingerprint import canonical_location_key, compute_fingerprint, normalize_text
from app.core.models import Base, JobPosting
from app.scrapers.engine import ScraperEngine


def test_fingerprint_normalization_and_location():
    # Normalization strips punctuation and legal suffixes
    assert normalize_text("Google India Pvt. Ltd.") == "google india"
    assert normalize_text("Amazon Development Centre (India) Private Limited") == "amazon development centre india"
    assert normalize_text("Acme, Inc.") == "acme"
    assert normalize_text("Microsoft Corp.") == "microsoft"
    assert normalize_text("TCS Technologies Ltd") == "tcs"
    assert normalize_text("Meta Platforms, LLC") == "meta platforms"

    # Location canonical keys
    assert canonical_location_key("Hyderabad, Telangana, India") == "hyderabad"
    assert canonical_location_key("Bengaluru, Karnataka") == "bengaluru"
    assert canonical_location_key("Bangalore") == "bengaluru"
    assert canonical_location_key("Pune, Maharashtra") == "pune"
    assert canonical_location_key("Mumbai, India") == "mumbai"
    assert canonical_location_key("Remote - India") == "remote-india"
    assert canonical_location_key("Remote (Worldwide)") == "remote"
    assert canonical_location_key("Unknown") == "unknown"
    assert canonical_location_key(None) == "unknown"


def test_same_role_different_locations_different_fingerprints():
    fp_hyd = compute_fingerprint("Acme Corp", "Backend Engineer", "Hyderabad")
    fp_blr = compute_fingerprint("Acme Corp", "Backend Engineer", "Bengaluru")
    assert fp_hyd != fp_blr

    # Same role from two different sources in same location gives identical fingerprint
    fp_ats = compute_fingerprint("Acme, Inc.", "Backend Engineer", "Hyderabad, India")
    fp_board = compute_fingerprint("Acme Inc", "Backend Engineer", "Hyderabad")
    assert fp_ats == fp_board


def test_wildcards_percent_and_underscore_do_not_match_other_companies():
    # In SQL ILIKE, 'Acme%' matches 'Acme Corp', 'Acme Systems', etc.
    # In deterministic fingerprinting, they have distinct hashes and exact equality prevents matching.
    fp_wild_pct = compute_fingerprint("Acme%Special", "Backend Engineer", "Hyderabad")
    fp_other = compute_fingerprint("Acme Corp", "Backend Engineer", "Hyderabad")
    assert fp_wild_pct != fp_other

    # In SQL ILIKE, 'A_B' matches 'AXB'
    fp_underscore = compute_fingerprint("A_B", "Backend Engineer", "Hyderabad")
    fp_axb = compute_fingerprint("AXB", "Backend Engineer", "Hyderabad")
    assert fp_underscore != fp_axb


@pytest.mark.asyncio
async def test_same_role_two_locations_creates_two_rows_and_two_sources_creates_one(tmp_path, monkeypatch):
    db_path = tmp_path / "test_dedup.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    test_engine = create_async_engine(db_url)
    test_session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr("app.scrapers.engine.async_session_factory", test_session_factory)

    engine = ScraperEngine()
    monkeypatch.setattr(engine.notifier, "dispatch_job_alert", lambda *args, **kwargs: False)

    # 1. Same role at "Stripe" in Hyderabad and Bengaluru (should produce 2 rows)
    # 2. Same role from 2 sources in Hyderabad (one from Greenhouse, one from Lever with different URLs)
    #    (should collapse to 1 row via fingerprint)
    raw_jobs = [
        {
            "title": "Staff Backend Engineer",
            "company": "Stripe",
            "location": "Hyderabad, Telangana",
            "url": "https://stripe.com/jobs/hyd-greenhouse",
            "source_platform": "Greenhouse",
            "description": "Python FastAPI PostgreSQL distributed systems.",
            "posted_date": "yesterday",
        },
        {
            "title": "Staff Backend Engineer",
            "company": "Stripe",
            "location": "Bengaluru, Karnataka",
            "url": "https://stripe.com/jobs/blr-greenhouse",
            "source_platform": "Greenhouse",
            "description": "Python FastAPI PostgreSQL distributed systems.",
            "posted_date": "yesterday",
        },
        {
            "title": "Staff Backend Engineer",
            "company": "Stripe, Inc.", # Will normalize to "stripe"
            "location": "Hyderabad",
            "url": "https://stripe.com/jobs/hyd-lever", # Different URL from Greenhouse
            "source_platform": "Lever",
            "description": "Python FastAPI PostgreSQL distributed systems.",
            "posted_date": "yesterday",
        },
    ]

    class MockScraper:
        async def scrape(self):
            return raw_jobs

    engine.scrapers = [MockScraper()]
    stats = await engine.run_discovery_cycle()

    assert stats["new_jobs"] == 2 # Hyderabad (1) + Bengaluru (1), Lever duplicate collapsed!

    async with test_session_factory() as session:
        res = await session.execute(select(JobPosting).order_by(JobPosting.location))
        jobs = res.scalars().all()
        assert len(jobs) == 2
        locations = [j.location for j in jobs]
        assert any("Hyderabad" in loc for loc in locations)
        assert any("Bengaluru" in loc for loc in locations)

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_company_with_percent_and_underscore_not_matching_others_in_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_wildcard.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    test_engine = create_async_engine(db_url)
    test_session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr("app.scrapers.engine.async_session_factory", test_session_factory)
    engine = ScraperEngine()
    monkeypatch.setattr(engine.notifier, "dispatch_job_alert", lambda *args, **kwargs: False)

    # In DB, we insert a company with 'AXB'
    async with test_session_factory() as session:
        fp_axb = compute_fingerprint("AXB", "Python Engineer", "Hyderabad")
        j = JobPosting(
            title="Python Engineer",
            company="AXB",
            location="Hyderabad",
            url="https://example.com/axb",
            source_platform="Web",
            fingerprint=fp_axb,
        )
        session.add(j)
        await session.commit()

    # Now scrape a company with 'A_B' (in SQL ILIKE this would match AXB)
    raw_jobs = [
        {
            "title": "Python Engineer",
            "company": "A_B",
            "location": "Hyderabad",
            "url": "https://example.com/a_b",
            "source_platform": "Web",
            "description": "Python, SQL backend developer",
            "posted_date": "yesterday",
        }
    ]

    class MockScraper:
        async def scrape(self):
            return raw_jobs

    engine.scrapers = [MockScraper()]
    stats = await engine.run_discovery_cycle()

    # Must NOT be dropped as a duplicate; A_B must be inserted as a new distinct job!
    assert stats["new_jobs"] == 1

    async with test_session_factory() as session:
        res = await session.execute(select(JobPosting))
        all_jobs = res.scalars().all()
        assert len(all_jobs) == 2
        companies = {j.company for j in all_jobs}
        assert "AXB" in companies
        assert "A_B" in companies

    await test_engine.dispose()
