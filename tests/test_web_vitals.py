import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.api.routes_telemetry import calculate_p75


def test_calculate_p75_percentile():
    # Empty
    assert calculate_p75([]) == 0.0

    # Values [100, 200, 300, 400] -> p75 is 300
    vals = [100.0, 200.0, 300.0, 400.0]
    p75 = calculate_p75(vals)
    assert p75 == 300.0


@pytest.mark.asyncio
async def test_web_vitals_ingest_and_summary():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Ingest samples
        payload_lcp = {
            "name": "LCP",
            "value": 1450.5,
            "rating": "good",
            "path": "/",
        }
        res_post = await client.post("/api/telemetry/web-vitals", json=payload_lcp)
        assert res_post.status_code == 200
        assert res_post.json()["status"] == "recorded"

        payload_cls = {
            "name": "CLS",
            "value": 0.02,
            "rating": "good",
            "path": "/tracker",
        }
        await client.post("/api/telemetry/web-vitals", json=payload_cls)

        # Retrieve summary
        res_get = await client.get("/api/telemetry/web-vitals")
        assert res_get.status_code == 200
        data = res_get.json()
        assert "LCP" in data["metrics"]
        assert "CLS" in data["metrics"]
        assert data["metrics"]["LCP"]["p75_value"] > 0
