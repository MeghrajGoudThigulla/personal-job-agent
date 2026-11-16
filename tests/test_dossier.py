import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from app.config import settings
from app.main import app
from app.core.database import async_session_factory
from app.core.models import JobPosting
from app.core.clock import utcnow
from app.core.fingerprint import compute_fingerprint
from app.intelligence.dossier import CompanyDossierGenerator


def test_dossier_generator_curated_and_inferred():
    generator = CompanyDossierGenerator()

    # 1. Curated company: Zerodha
    dossier_zerodha = generator.generate_dossier(
        company="Zerodha",
        job_title="Senior Python Backend Engineer",
        description="Low latency order routing and PostgreSQL distributed systems."
    )
    assert dossier_zerodha["is_curated"] is True
    assert "zerodha.com" in dossier_zerodha["domain"]
    assert len(dossier_zerodha["scale_challenges"]) >= 3
    assert len(dossier_zerodha["reverse_interview_questions"]) == 4

    # Check LinkedIn assets
    li = dossier_zerodha["linkedin_outreach"]
    assert len(li["connection_request_note"]) < 300
    assert "Zerodha" in li["connection_request_note"]
    assert "Meghraj" in li["recruiter_inmail"]

    # 2. Inferred company
    dossier_startup = generator.generate_dossier(
        company="Nexus AI",
        job_title="Lead Platform Architect",
        description="Building enterprise GenAI agents with FastAPI, Redis, and AWS."
    )
    assert dossier_startup["is_curated"] is False
    assert "nexusai.com" in dossier_startup["domain"]
    assert "FastAPI" in dossier_startup["tech_stack"]["backend"]
    assert len(dossier_startup["reverse_interview_questions"]) == 4


@pytest.mark.asyncio
async def test_job_dossier_api_endpoint(monkeypatch):
    now = utcnow()
    unique_url = f"https://postman.com/careers/{uuid.uuid4().hex[:6]}"
    async with async_session_factory() as session:
        job = JobPosting(
            title="Backend Systems Engineer",
            company="Postman",
            location="Bangalore",
            url=unique_url,
            source_platform="Web",
            match_score=92.0,
            discovered_at=now,
            posted_at=now,
            fingerprint=compute_fingerprint("Postman", "Backend Systems Engineer", "Bangalore"),
            description="Developing high-scale distributed API infrastructure in Go and Python.",
        )
        session.add(job)
        await session.commit()
        job_id = job.id

    settings.APP_PASSWORD = "supersecretpassword123"
    headers = {"Authorization": "Bearer supersecretpassword123"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(f"/api/jobs/{job_id}/dossier", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["job_id"] == job_id
        assert data["company"] == "Postman"
        assert "postman.com" in data["domain"]
        assert "linkedin_outreach" in data
        assert "connection_request_note" in data["linkedin_outreach"]
