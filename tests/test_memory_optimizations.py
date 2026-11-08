import asyncio
import os
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core import clock
from app.core.models import Base, JobPosting
from app.core.system import get_process_memory_mb
from app.intelligence.pdf_compiler import PDFCompiler
from app.main import app
from app.scrapers.engine import ScraperEngine


def test_get_process_memory_mb():
    """Verify get_process_memory_mb returns a valid float on Linux."""
    rss = get_process_memory_mb()
    assert isinstance(rss, float)
    assert rss >= 0.0


def test_pdf_compile_disabled_fallback(tmp_path, monkeypatch):
    """Verify that when PDF_COMPILE_ENABLED is false, compile_resume writes HTML fallback and succeeds."""
    monkeypatch.setattr(settings, "PDF_COMPILE_ENABLED", False)

    compiler = PDFCompiler(output_dir=tmp_path / "resumes")
    res = compiler.compile_resume(
        job_id=999,
        company_slug="testcorp",
        role_title="Backend Engineer",
        latex_content="\\documentclass{article}\\begin{document}Hello World\\end{document}",
    )

    assert res["success"] is True
    assert res["artifact_type"] == "html"
    assert res["pdf_generated"] is False
    assert "pdf_path" in res
    assert res["pdf_path"].endswith(".html")
    assert os.path.exists(res["pdf_path"])
    with open(res["pdf_path"], "r", encoding="utf-8") as f:
        html = f.read()
        assert "Backend_Engineer" in html
        assert "testcorp" in html


def test_job_posting_to_dict_defer_description():
    """Verify JobPosting.to_dict respects include_description=False."""
    job = JobPosting(
        id=1,
        title="Software Engineer",
        company="Acme Corp",
        location="Remote",
        description="A" * 5000,
        match_score=85.0,
        match_tier="Tier 1",
    )

    dict_with_desc = job.to_dict(include_description=True)
    assert "description" in dict_with_desc
    assert dict_with_desc["description"] == "A" * 5000

    dict_without_desc = job.to_dict(include_description=False)
    assert "description" not in dict_without_desc
    assert dict_without_desc["title"] == "Software Engineer"


@pytest.mark.asyncio
async def test_engine_truncates_long_descriptions(tmp_path, monkeypatch):
    """Verify ScraperEngine truncates descriptions exceeding 8000 characters."""
    db_path = tmp_path / "test_engine_trunc.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    test_engine = create_async_engine(db_url)
    test_session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr("app.scrapers.engine.async_session_factory", test_session_factory)
    monkeypatch.setattr(settings, "AUTO_TAILOR_HIGH_MATCH", False)

    engine = ScraperEngine(cycle_lock=asyncio.Lock())
    monkeypatch.setattr(engine.notifier, "dispatch_job_alert", lambda *args, **kwargs: False)

    huge_description = "Python FastAPI Docker " * 800  # ~17,600 chars
    mock_jobs = [
        {
            "title": "Backend Python Developer",
            "company": "BigDesc Corp",
            "location": "Hyderabad, India",
            "url": "https://example.com/jobs/big-desc-1",
            "source_platform": "Direct ATS",
            "description": huge_description,
            "posted_date": clock.utcnow().strftime("%Y-%m-%d"),
        }
    ]

    class MockScraper:
        name = "MockScraper"

        async def scrape(self):
            return mock_jobs

    engine.scrapers = [MockScraper()]

    stats = await engine.run_discovery_cycle()
    assert stats["new_jobs"] == 1
    assert "memory_rss_mb" in stats
    assert stats["memory_rss_mb"] >= 0.0

    async with test_session_factory() as session:
        result = await session.get(JobPosting, 1)
        assert result is not None
        assert len(result.description) <= 8000
        assert result.description == huge_description[:8000]


@pytest.mark.asyncio
async def test_engine_cycle_lock_prevents_overlap():
    """Verify ScraperEngine returns busy status if a cycle is already active."""
    lock = asyncio.Lock()
    engine = ScraperEngine(cycle_lock=lock)

    # Acquire lock simulating an active discovery cycle
    await lock.acquire()
    try:
        stats = await engine.run_discovery_cycle()
        assert stats["status"] == "busy"
        assert stats["new_jobs"] == 0
        assert "Discovery cycle already in progress" in stats["message"]
    finally:
        lock.release()


@pytest.mark.asyncio
async def test_health_detailed_returns_memory_rss():
    """Verify /api/health/detailed reports memory_rss_mb."""
    settings.APP_PASSWORD = "testpassword12345"
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {settings.APP_PASSWORD}"}

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/health/detailed", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "memory_rss_mb" in data
        assert isinstance(data["memory_rss_mb"], (int, float))
        assert data["memory_rss_mb"] >= 0.0
