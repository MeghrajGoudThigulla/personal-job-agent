import json
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from app.config import settings
from app.core.database import async_session_factory, engine, init_db
from app.core.models import JobPosting
from app.intelligence.company_research import CompanyResearcher
from app.main import app

AUTH_HEADERS = {"Authorization": "Bearer supersecretpassword123"}


@pytest.fixture(autouse=True)
def configure_test_auth():
    settings.APP_PASSWORD = "supersecretpassword123"
    yield


def test_known_company_curated_signals():
    researcher = CompanyResearcher()
    res = researcher.research_company(
        company="Zerodha Broking Ltd",
        job_title="Backend Developer",
        job_url="https://zerodha.com/careers/backend-1",
        description="Looking for Python and Postgres engineers."
    )

    assert res["is_curated"] is True
    assert res["domain"] == "zerodha.com"
    assert "Fintech" in res["archetype"]
    assert len(res["interview_angles"]) >= 3
    assert any("latency" in a.lower() or "postgres" in a.lower() or "pragmatic" in a.lower() for a in res["interview_angles"])


def test_unknown_company_heuristic_signals():
    researcher = CompanyResearcher()
    res = researcher.research_company(
        company="MediFlow Systems",
        job_title="Senior AI Engineer",
        job_url="https://jobs.mediflow.io/clinical-backend",
        description="Building Clinical healthcare RAG pipelines for hospital patient records."
    )

    assert res["is_curated"] is False
    assert "mediflow" in res["domain"]
    assert "Health" in res["archetype"]
    assert len(res["interview_angles"]) >= 3


@pytest.mark.asyncio
async def test_company_research_api_and_mcp_endpoints():
    await init_db()

    uid = uuid.uuid4().hex[:6]
    async with async_session_factory() as db:
        job = JobPosting(
            title="Senior Payments Architect",
            company="Razorpay",
            location="Bangalore, India",
            url=f"https://razorpay.example/jobs/{uid}",
            source_platform="Ashby",
            description="High-throughput payment gateway architecture.",
            match_score=95.0,
            status="new"
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        job_id = job.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. API route
        res_api = await ac.get(f"/api/jobs/{job_id}/company-research", headers=AUTH_HEADERS)
        assert res_api.status_code == 200
        data = res_api.json()
        assert data["job_id"] == job_id
        assert data["company"] == "Razorpay"
        assert "razorpay.com" in data["domain"]
        assert "Fintech" in data["archetype"]
        assert len(data["interview_angles"]) >= 3

        # 2. 404 for missing job
        res_404 = await ac.get("/api/jobs/999999/company-research", headers=AUTH_HEADERS)
        assert res_404.status_code == 404

        # 3. MCP tool call
        mcp_payload = {
            "jsonrpc": "2.0",
            "id": 101,
            "method": "tools/call",
            "params": {
                "name": "research_company",
                "arguments": {"job_id": job_id}
            }
        }
        res_mcp = await ac.post("/api/mcp", json=mcp_payload, headers=AUTH_HEADERS)
        assert res_mcp.status_code == 200
        mcp_content = json.loads(res_mcp.json()["result"]["content"][0]["text"])
        assert mcp_content["company"] == "Razorpay"
        assert "razorpay.com" in mcp_content["domain"]

    await engine.dispose()
