import json
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from app.config import settings
from app.core.database import async_session_factory, engine, init_db
from app.core.models import JobPosting
from app.intelligence.salary_benchmarks import SalaryBenchmarker
from app.main import app

AUTH_HEADERS = {"Authorization": "Bearer supersecretpassword123"}


@pytest.fixture(autouse=True)
def configure_test_auth():
    settings.APP_PASSWORD = "supersecretpassword123"
    yield


def test_stated_salary_extraction():
    benchmarker = SalaryBenchmarker()

    # 1. LPA
    s1 = benchmarker.extract_stated_salary("Salary range is 22 - 35 LPA based on experience.")
    assert s1 is not None
    assert s1["min"] == 22.0
    assert s1["max"] == 35.0
    assert s1["currency"] == "INR"
    assert s1["formatted"] == "₹22.0 - ₹35.0 LPA"

    # 2. USD K
    s2 = benchmarker.extract_stated_salary("Compensation: $120k - $160k annual base.")
    assert s2 is not None
    assert s2["min"] == 120000
    assert s2["max"] == 160000
    assert s2["currency"] == "USD"

    # 3. Numeric INR
    s3 = benchmarker.extract_stated_salary("Budget: ₹1,800,000 - ₹2,800,000 per annum")
    assert s3 is not None
    assert s3["min"] == 18.0
    assert s3["max"] == 28.0

    # 4. None
    assert benchmarker.extract_stated_salary("Competitive market salary") is None


def test_seniority_determination_and_benchmarking():
    benchmarker = SalaryBenchmarker()

    assert benchmarker.determine_seniority("Senior Software Engineer") == "senior"
    assert benchmarker.determine_seniority("Tech Lead / Distributed Systems") == "lead"
    assert benchmarker.determine_seniority("Staff Backend Engineer") == "staff"
    assert benchmarker.determine_seniority("Junior Python Developer") == "junior"
    assert benchmarker.determine_seniority("Software Engineer") == "mid"

    bench = benchmarker.benchmark(
        job_title="Senior Backend Architect",
        location="Bangalore, India",
        description="High-concurrency payment engine."
    )
    assert "₹" in bench["benchmark_inr_lpa"]
    assert "$" in bench["benchmark_usd_annual"]
    assert "Senior" in bench["seniority_tier"] or "Lead" in bench["seniority_tier"]
    assert len(bench["negotiation_tip"]) > 20


@pytest.mark.asyncio
async def test_salary_benchmark_api_and_mcp_endpoints():
    await init_db()

    uid = uuid.uuid4().hex[:6]
    async with async_session_factory() as db:
        job = JobPosting(
            title="Senior Platform Engineer",
            company="Nexar Tech",
            location="Hyderabad, India",
            url=f"https://nexar.example/jobs/{uid}",
            source_platform="Naukri",
            match_score=92.0,
            description="Offering 25 - 40 LPA for senior systems developer with FastAPI and Postgres.",
            status="new"
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        job_id = job.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. API route
        res_api = await ac.get(f"/api/jobs/{job_id}/salary-benchmark", headers=AUTH_HEADERS)
        assert res_api.status_code == 200
        data = res_api.json()
        assert data["job_id"] == job_id
        assert data["has_stated_salary"] is True
        assert "25.0 - ₹40.0 LPA" in data["stated_salary"]
        assert "benchmark_inr_lpa" in data

        # 2. 404 for missing
        res_404 = await ac.get("/api/jobs/999999/salary-benchmark", headers=AUTH_HEADERS)
        assert res_404.status_code == 404

        # 3. MCP tool call
        mcp_payload = {
            "jsonrpc": "2.0",
            "id": 202,
            "method": "tools/call",
            "params": {
                "name": "benchmark_salary",
                "arguments": {"job_id": job_id}
            }
        }
        res_mcp = await ac.post("/api/mcp", json=mcp_payload, headers=AUTH_HEADERS)
        assert res_mcp.status_code == 200
        mcp_content = json.loads(res_mcp.json()["result"]["content"][0]["text"])
        assert mcp_content["has_stated_salary"] is True
        assert "25.0 - ₹40.0 LPA" in mcp_content["stated_salary"]

    await engine.dispose()
