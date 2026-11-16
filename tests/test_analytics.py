import uuid
import pytest
from httpx import ASGITransport, AsyncClient
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
async def test_analytics_funnel_empty_and_seeded():
    await init_db()

    # Seed jobs
    uid = uuid.uuid4().hex[:6]
    async with async_session_factory() as db:
        # Job 1: High match, applied
        j1 = JobPosting(
            title="Backend Architect",
            company="AlphaCorp",
            location="Remote, India",
            url=f"https://alphacorp.example/jobs/{uid}-1",
            source_platform="Ashby",
            match_score=85.0,
            status="applied",
            applied_at=None,
            role_category="Backend Engineering",
        )
        # Job 2: High match, interviewing
        j2 = JobPosting(
            title="Senior Python Engineer",
            company="BetaTech",
            location="Bangalore",
            url=f"https://betatech.example/jobs/{uid}-2",
            source_platform="Naukri",
            match_score=90.0,
            status="interviewing",
            interview_stage="Round 1 (Technical)",
            role_category="Backend Engineering",
        )
        # Job 3: Low match, new
        j3 = JobPosting(
            title="Junior QA",
            company="GammaInc",
            location="Hyderabad",
            url=f"https://gammainc.example/jobs/{uid}-3",
            source_platform="Indeed",
            match_score=40.0,
            status="new",
            role_category="Quality Assurance",
        )
        db.add_all([j1, j2, j3])
        await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Check API funnel
        res = await ac.get("/api/analytics/funnel", headers=AUTH_HEADERS)
        assert res.status_code == 200
        data = res.json()

        assert "funnel" in data
        assert "rates" in data
        assert "sources" in data
        assert "categories" in data

        funnel = data["funnel"]
        assert funnel["discovered"] >= 3
        assert funnel["qualified"] >= 2
        assert funnel["applied"] >= 2
        assert funnel["interviewing"] >= 1

        # Check HTML view
        res_html = await ac.get("/analytics", headers=AUTH_HEADERS)
        assert res_html.status_code == 200
        assert "text/html" in res_html.headers.get("content-type", "")
        assert "Application Funnel & Conversion" in res_html.text
        assert "Pipeline Conversion Funnel" in res_html.text
