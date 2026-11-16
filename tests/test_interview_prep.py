import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from app.config import settings
from app.main import app
from app.core.database import async_session_factory, init_db
from app.core.models import JobPosting
from app.intelligence.interview_prep import InterviewPrepGenerator


AUTH_HEADERS = {"Authorization": "Bearer supersecretpassword123"}

@pytest.fixture(autouse=True)
def configure_test_auth():
    settings.APP_PASSWORD = "supersecretpassword123"
    yield



@pytest.mark.asyncio
async def test_deterministic_interview_prep_generation():
    generator = InterviewPrepGenerator()
    pack = generator.generate_deterministic_pack(
        job_title="Senior Backend Engineer",
        company="Acme Cloud",
        matched_skills=["Python", "FastAPI", "PostgreSQL"]
    )

    assert pack["job_title"] == "Senior Backend Engineer"
    assert pack["company"] == "Acme Cloud"
    assert len(pack["technical_questions"]) == 3
    assert len(pack["behavioral_questions"]) == 3
    assert len(pack["questions_to_ask"]) == 3
    assert "# 🎯 Interview Preparation Pack" in pack["markdown"]
    assert "STAR Framework" in pack["markdown"]


@pytest.mark.asyncio
async def test_llm_interview_prep_fallback_on_error():
    class BrokenLLM:
        async def generate(self, *args, **kwargs):
            raise RuntimeError("API timeout")

    generator = InterviewPrepGenerator(llm_client=BrokenLLM())
    pack = await generator.generate(
        job_title="Platform Engineer",
        company="Nexus AI",
        description="Looking for distributed systems architect.",
        matched_skills=["Docker", "PostgreSQL"]
    )

    assert pack["job_title"] == "Platform Engineer"
    assert pack["company"] == "Nexus AI"
    assert len(pack["technical_questions"]) >= 1


@pytest.mark.asyncio
async def test_interview_prep_and_cover_letter_api_endpoints():
    await init_db()

    # Seed job posting
    unique_id = uuid.uuid4().hex[:8]
    async with async_session_factory() as db:
        job = JobPosting(
            title="Lead Systems Architect",
            company="Starlight Tech",
            location="Remote, India",
            url=f"https://starlight.example/jobs/arch-{unique_id}",
            source_platform="Ashby",
            description="Seeking architect with deep FastAPI and Postgres experience.",
            match_score=92.0,
            match_reason='{"matched_skills": ["Python", "FastAPI", "PostgreSQL"]}'
        )

        db.add(job)
        await db.commit()
        await db.refresh(job)
        job_id = job.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Test Prep Pack endpoint
        res_prep = await ac.get(f"/api/jobs/{job_id}/prep-pack", headers=AUTH_HEADERS)
        assert res_prep.status_code == 200
        prep_data = res_prep.json()
        assert prep_data["company"] == "Starlight Tech"
        assert "technical_questions" in prep_data
        assert "behavioral_questions" in prep_data
        assert "markdown" in prep_data

        # Test Cover Letter endpoint
        res_letter = await ac.get(f"/api/jobs/{job_id}/cover-letter", headers=AUTH_HEADERS)
        assert res_letter.status_code == 200
        letter_data = res_letter.json()
        assert letter_data["company"] == "Starlight Tech"
        assert "cover_letter" in letter_data
        assert "Thigulla Meghraj Goud" in letter_data["cover_letter"]
        assert "Dear Starlight Tech Hiring Team" in letter_data["cover_letter"]

        # Test 404 for missing job
        res_404_prep = await ac.get("/api/jobs/999999/prep-pack", headers=AUTH_HEADERS)
        assert res_404_prep.status_code == 404
        res_404_letter = await ac.get("/api/jobs/999999/cover-letter", headers=AUTH_HEADERS)
        assert res_404_letter.status_code == 404

