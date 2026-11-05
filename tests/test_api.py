import uuid
import pytest
import json
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import init_db, async_session_factory
from app.core.models import JobPosting, TailoredApplication

@pytest.mark.asyncio
async def test_health_endpoint():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["service"] == "personal-job-agent"

        # Also verify HEAD /health
        res_head = await ac.head("/health")
        assert res_head.status_code == 200

@pytest.mark.asyncio
async def test_dashboard_endpoint():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/")
        assert res.status_code == 200
        assert "text/html" in res.headers.get("content-type", "")
        assert "Personal Job Agent" in res.text

        # Verify HEAD / returns 200
        res_head = await ac.head("/")
        assert res_head.status_code == 200

@pytest.mark.asyncio
async def test_settings_and_trace_views():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res_settings = await ac.get("/settings")
        assert res_settings.status_code == 200
        assert "text/html" in res_settings.headers.get("content-type", "")

        res_trace = await ac.get("/trace")
        assert res_trace.status_code == 200
        assert "text/html" in res_trace.headers.get("content-type", "")

@pytest.mark.asyncio
async def test_job_detail_endpoint():
    await init_db()
    # Seed a test job posting
    async with async_session_factory() as db:
        job = JobPosting(
            title="Senior AI Engineer",
            company="TestCorp",
            location="Remote",
            source_platform="greenhouse",
            url=f"https://testcorp.com/apply/{uuid.uuid4().hex}",
            description="We need an expert in Python, LLM orchestration, and distributed systems.",
            role_category="AI Engineer",
            match_score=85.5,
            match_reason=json.dumps({"pros": ["Strong Python", "LLM background"], "skills_matched": ["Python", "FastAPI"]})
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        job_id = job.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Existing job
        res = await ac.get(f"/jobs/{job_id}")
        assert res.status_code == 200
        assert "text/html" in res.headers.get("content-type", "")
        assert "Senior AI Engineer" in res.text
        assert "TestCorp" in res.text

        # Non-existing job
        res_404 = await ac.get("/jobs/9999999")
        assert res_404.status_code == 404

@pytest.mark.asyncio
async def test_scraper_queries_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/scraper/queries")
        assert res.status_code == 200
        data = res.json()
        assert "roles" in data
        assert len(data["roles"]) == 11
