import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from app.config import settings
from app.core.database import async_session_factory, init_db, engine
from app.core.models import JobPosting

from app.intelligence.skill_gap import SkillGapDetector
from app.main import app

AUTH_HEADERS = {"Authorization": "Bearer supersecretpassword123"}


@pytest.fixture(autouse=True)
def configure_test_auth():
    settings.APP_PASSWORD = "supersecretpassword123"
    yield


def test_skill_gap_detector_single_job_analysis():
    detector = SkillGapDetector()
    res = detector.analyze_job(
        job_title="Lead Distributed Systems Engineer",
        description="Looking for an architect with Kafka, Kubernetes, and FastAPI expertise.",
        matched_skills=["Python", "FastAPI"],
        missing_skills=["Kafka", "Kubernetes"]
    )

    assert res["job_title"] == "Lead Distributed Systems Engineer"
    assert res["total_matched"] == 2
    assert res["total_gaps"] == 2

    gap_skills = [g["skill"].lower() for g in res["gaps"]]
    assert "kafka" in gap_skills
    assert "kubernetes" in gap_skills

    kafka_gap = next(g for g in res["gaps"] if g["skill"].lower() == "kafka")
    assert "Redis" in kafka_gap["adjacent_skill"]
    assert "event-driven" in kafka_gap["quick_poc"].lower()
    assert len(kafka_gap["bridging_talking_point"]) > 20


def test_skill_gap_detector_market_aggregation():
    detector = SkillGapDetector()
    metadata = [
        {"matched_skills": ["python"], "missing_skills": ["kafka", "kubernetes"]},
        {"matched_skills": ["fastapi"], "missing_skills": ["kafka", "aws"]},
        {"matched_skills": ["python", "docker"], "missing_skills": ["kafka", "graphql"]},
    ]

    ranked = detector.aggregate_market_gaps(metadata)
    assert len(ranked) >= 3

    # Kafka appeared in 3/3 jobs -> 100% prevalence
    top_skill = ranked[0]
    assert top_skill["skill"] == "Kafka"
    assert top_skill["demand_count"] == 3
    assert top_skill["prevalence_pct"] == 100.0



@pytest.mark.asyncio
async def test_skill_gap_api_endpoints():
    await init_db()

    uid = uuid.uuid4().hex[:6]
    async with async_session_factory() as db:
        job = JobPosting(
            title="Senior Platform Architect",
            company="CloudCorp",
            location="Remote, India",
            url=f"https://cloudcorp.example/jobs/{uid}",
            source_platform="Ashby",
            description="Requires Python, FastAPI, Kubernetes, and AWS.",
            match_score=88.0,
            match_reason='{"matched_skills": ["Python", "FastAPI"], "missing_skills": ["Kubernetes", "AWS"]}'
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        job_id = job.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Job-level skill gap
        res_job_gap = await ac.get(f"/api/jobs/{job_id}/skill-gap", headers=AUTH_HEADERS)
        assert res_job_gap.status_code == 200
        data = res_job_gap.json()
        assert data["job_id"] == job_id
        assert data["company"] == "CloudCorp"
        assert data["total_gaps"] == 2
        assert any(g["skill"].lower() == "kubernetes" for g in data["gaps"])

        # 2. Market-wide skill gaps
        res_market = await ac.get("/api/analytics/skill-gaps", headers=AUTH_HEADERS)
        assert res_market.status_code == 200
        market_data = res_market.json()
        assert isinstance(market_data, list)
        assert len(market_data) > 0
        assert any(g["skill"].lower() == "kubernetes" for g in market_data)

    await engine.dispose()


