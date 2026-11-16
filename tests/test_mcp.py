import json
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from app.config import settings
from app.core.database import async_session_factory, engine, init_db
from app.core.models import JobPosting
from app.main import app

AUTH_HEADERS = {"Authorization": "Bearer supersecretpassword123"}


@pytest.fixture(autouse=True)
def configure_test_auth():
    settings.APP_PASSWORD = "supersecretpassword123"
    yield


@pytest.mark.asyncio
async def test_mcp_tools_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/mcp/tools", headers=AUTH_HEADERS)
        assert res.status_code == 200
        data = res.json()
        assert "tools" in data
        tool_names = [t["name"] for t in data["tools"]]
        assert "search_jobs" in tool_names
        assert "generate_cover_letter" in tool_names
        assert "generate_interview_prep" in tool_names
        assert "analyze_skill_gaps" in tool_names
        assert "update_application_stage" in tool_names


@pytest.mark.asyncio
async def test_mcp_protocol_lifecycle_and_tools_execution():
    await init_db()

    # Seed test job
    uid = uuid.uuid4().hex[:6]
    async with async_session_factory() as db:
        job = JobPosting(
            title="Senior Distributed Systems Architect",
            company="Orion Labs",
            location="Remote, India",
            url=f"https://orionlabs.example/jobs/{uid}",
            source_platform="LinkedIn",
            match_score=94.0,
            description="Seeking Python, FastAPI, and Kafka engineer for high-concurrency systems.",
            match_reason='{"matched_skills": ["Python", "FastAPI"], "missing_skills": ["Kafka"]}',
            status="new"
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        job_id = job.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. initialize
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"}
        }
        res_init = await ac.post("/api/mcp", json=init_payload, headers=AUTH_HEADERS)
        assert res_init.status_code == 200
        data_init = res_init.json()
        assert data_init["result"]["serverInfo"]["name"] == "personal-job-agent-mcp"

        # 2. ping
        res_ping = await ac.post("/api/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "ping"}, headers=AUTH_HEADERS)
        assert res_ping.status_code == 200
        assert res_ping.json()["result"] == {}

        # 3. tools/list
        res_list = await ac.post("/api/mcp", json={"jsonrpc": "2.0", "id": 3, "method": "tools/list"}, headers=AUTH_HEADERS)
        assert res_list.status_code == 200
        tools = res_list.json()["result"]["tools"]
        assert len(tools) >= 5

        # 4. tools/call: search_jobs
        search_call = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "search_jobs",
                "arguments": {"query": "Orion Labs", "min_score": 80, "limit": 10}
            }
        }

        res_search = await ac.post("/api/mcp", json=search_call, headers=AUTH_HEADERS)
        assert res_search.status_code == 200
        search_content = json.loads(res_search.json()["result"]["content"][0]["text"])
        assert isinstance(search_content, list)
        assert any(j["id"] == job_id for j in search_content)

        # 5. tools/call: get_job_details
        details_call = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "get_job_details",
                "arguments": {"job_id": job_id}
            }
        }
        res_details = await ac.post("/api/mcp", json=details_call, headers=AUTH_HEADERS)
        assert res_details.status_code == 200
        details_content = json.loads(res_details.json()["result"]["content"][0]["text"])
        assert details_content["id"] == job_id
        assert details_content["company"] == "Orion Labs"

        # 6. tools/call: generate_cover_letter
        letter_call = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "generate_cover_letter",
                "arguments": {"job_id": job_id}
            }
        }
        res_letter = await ac.post("/api/mcp", json=letter_call, headers=AUTH_HEADERS)
        assert res_letter.status_code == 200
        letter_text = res_letter.json()["result"]["content"][0]["text"]
        assert "Dear Orion Labs Hiring Team" in letter_text

        # 7. tools/call: generate_interview_prep
        prep_call = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "generate_interview_prep",
                "arguments": {"job_id": job_id}
            }
        }
        res_prep = await ac.post("/api/mcp", json=prep_call, headers=AUTH_HEADERS)
        assert res_prep.status_code == 200
        prep_text = res_prep.json()["result"]["content"][0]["text"]
        assert "Interview Preparation Pack" in prep_text

        # 8. tools/call: analyze_skill_gaps
        gap_call = {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {
                "name": "analyze_skill_gaps",
                "arguments": {"job_id": job_id}
            }
        }
        res_gap = await ac.post("/api/mcp", json=gap_call, headers=AUTH_HEADERS)
        assert res_gap.status_code == 200
        gap_data = json.loads(res_gap.json()["result"]["content"][0]["text"])
        assert any(g["skill"].lower() == "kafka" for g in gap_data["gaps"])

        # 9. tools/call: update_application_stage
        stage_call = {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {
                "name": "update_application_stage",
                "arguments": {
                    "job_id": job_id,
                    "status": "interviewing",
                    "interview_stage": "Technical Round 1",
                    "notes": "Spoke with VP of Engineering, focus on Kafka consumer scaling."
                }
            }
        }
        res_stage = await ac.post("/api/mcp", json=stage_call, headers=AUTH_HEADERS)
        assert res_stage.status_code == 200
        assert "Updated job" in res_stage.json()["result"]["content"][0]["text"]

        # 10. Unknown method returns -32601
        res_unknown = await ac.post("/api/mcp", json={"jsonrpc": "2.0", "id": 10, "method": "nonexistent_method"}, headers=AUTH_HEADERS)
        assert res_unknown.status_code == 200
        assert res_unknown.json()["error"]["code"] == -32601

    await engine.dispose()
