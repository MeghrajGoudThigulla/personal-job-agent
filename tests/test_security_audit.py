import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.api.routes_security import perform_security_audit


@pytest.mark.asyncio
async def test_security_headers_present():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        assert "Content-Security-Policy" in res.headers
        assert "frame-ancestors 'none'" in res.headers["Content-Security-Policy"]
        assert res.headers.get("X-Content-Type-Options") == "nosniff"
        assert res.headers.get("X-Frame-Options") == "DENY"
        assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "camera=()" in res.headers.get("Permissions-Policy", "")


def test_perform_security_audit_evaluation():
    report = perform_security_audit()
    assert report["status"] in ("secure", "needs_attention")
    assert report["grade"] in ("A+", "A", "B")
    assert report["score"] >= 80.0
    assert report["total_controls"] == 12
    assert report["passed_controls"] >= 10
    assert any(c["control"] == "Prompt Injection & Invisible Character Defense" for c in report["controls"])
    assert any(c["control"] == "CSRF Mitigation on Mutating Endpoints" for c in report["controls"])


@pytest.mark.asyncio
async def test_security_audit_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/security/audit")
        assert res.status_code == 200
        data = res.json()
        assert data["grade"] in ("A+", "A")
        assert data["total_controls"] == 12
