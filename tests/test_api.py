import uuid
import pytest
import json
from httpx import AsyncClient, ASGITransport
from app.config import settings
from app.core.database import async_session_factory, init_db
from app.core.models import JobPosting
from app.main import app

AUTH_HEADERS = {"Authorization": "Bearer supersecretpassword123"}

@pytest.fixture(autouse=True)
def configure_test_auth():
    settings.APP_PASSWORD = "supersecretpassword123"
    yield

@pytest.mark.asyncio
async def test_health_endpoint():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data == {"status": "ok"}

        # Also verify HEAD /health
        res_head = await ac.head("/health")
        assert res_head.status_code == 200

        # Verify /health/live
        res_live = await ac.get("/health/live")
        assert res_live.status_code == 200
        assert res_live.json() == {"status": "ok"}

        # Verify /health/ready
        res_ready = await ac.get("/health/ready")
        assert res_ready.status_code == 200
        assert res_ready.json() == {"status": "ready"}

@pytest.mark.asyncio
async def test_dashboard_endpoint():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/", headers=AUTH_HEADERS)
        assert res.status_code == 200
        assert "text/html" in res.headers.get("content-type", "")
        assert "Personal Job Agent" in res.text

        # Verify HEAD / returns 200
        res_head = await ac.head("/", headers=AUTH_HEADERS)
        assert res_head.status_code == 200

@pytest.mark.asyncio
async def test_settings_and_trace_views():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res_settings = await ac.get("/settings", headers=AUTH_HEADERS)
        assert res_settings.status_code == 200
        assert "text/html" in res_settings.headers.get("content-type", "")

        res_trace = await ac.get("/trace", headers=AUTH_HEADERS)
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
        res = await ac.get(f"/jobs/{job_id}", headers=AUTH_HEADERS)
        assert res.status_code == 200
        assert "text/html" in res.headers.get("content-type", "")
        assert "Senior AI Engineer" in res.text
        assert "TestCorp" in res.text

        # Non-existing job
        res_404 = await ac.get("/jobs/9999999", headers=AUTH_HEADERS)
        assert res_404.status_code == 404

@pytest.mark.asyncio
async def test_scraper_queries_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/scraper/queries", headers=AUTH_HEADERS)
        assert res.status_code == 200
        data = res.json()
        assert "roles" in data
        assert len(data["roles"]) == 11

@pytest.mark.asyncio
async def test_auth_enforcement_when_password_set():
    from app.config import settings
    # Set APP_PASSWORD
    settings.APP_PASSWORD = "supersecretpassword123"
    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Health check is always public (200)
            res_health = await ac.get("/health")
            assert res_health.status_code == 200

            # 2. Unauthenticated API call returns 401
            res_api = await ac.get("/api/scraper/queries")
            assert res_api.status_code == 401

            # 3. Unauthenticated Web UI redirects to /login (303)
            res_ui = await ac.get("/", follow_redirects=False)
            assert res_ui.status_code == 303
            assert res_ui.headers["location"] == "/login"

            # 4. Authenticated API call with Bearer succeeds (200)
            res_auth_api = await ac.get("/api/scraper/queries", headers={"Authorization": f"Bearer {settings.APP_PASSWORD}"})
            assert res_auth_api.status_code == 200

            # 5. Authenticated Web UI call with Session Cookie succeeds (200)
            res_auth_ui = await ac.get("/", cookies={settings.ADMIN_SESSION_COOKIE: settings.APP_PASSWORD})
            assert res_auth_ui.status_code == 200
    finally:
        # Reset password to blank for other tests
        settings.APP_PASSWORD = ""

@pytest.mark.asyncio
async def test_cleanup_purges_old_jobs_and_preserves_applied():
    from datetime import datetime, timezone, timedelta
    from app.core.cleanup import purge_old_records
    await init_db()

    # Seed an old job (70 days ago) with status 'new' -> should be deleted
    # Seed an old job (70 days ago) with status 'applied' -> should be preserved
    # Seed a recent job (5 days ago) -> should be preserved
    async with async_session_factory() as db:
        old_job = JobPosting(
            title="Old Python Dev",
            company="OldCorp",
            location="Remote",
            url=f"https://oldcorp.com/job/{uuid.uuid4().hex}",
            source_platform="ashby",
            status="new",
            discovered_at=datetime.now(timezone.utc) - timedelta(days=70)
        )
        applied_job = JobPosting(
            title="Applied Role",
            company="DreamCorp",
            location="Remote",
            url=f"https://dreamcorp.com/job/{uuid.uuid4().hex}",
            source_platform="ashby",
            status="applied",
            discovered_at=datetime.now(timezone.utc) - timedelta(days=70)
        )
        recent_job = JobPosting(
            title="Recent Role",
            company="FreshCorp",
            location="Remote",
            url=f"https://freshcorp.com/job/{uuid.uuid4().hex}",
            source_platform="ashby",
            status="new",
            discovered_at=datetime.now(timezone.utc) - timedelta(days=5)
        )
        db.add_all([old_job, applied_job, recent_job])
        await db.commit()
        old_id, applied_id, recent_id = old_job.id, applied_job.id, recent_job.id

    # Run cleanup with 60 days retention
    summary = await purge_old_records(retention_days=60, preserve_applied=True)
    assert summary["status"] == "success"
    assert summary["deleted_jobs"] >= 1

    # Verify old_job was deleted, applied_job and recent_job remain
    async with async_session_factory() as db:
        assert (await db.get(JobPosting, old_id)) is None
        assert (await db.get(JobPosting, applied_id)) is not None
        assert (await db.get(JobPosting, recent_id)) is not None
