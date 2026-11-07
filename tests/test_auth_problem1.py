from httpx import ASGITransport, AsyncClient
import pytest
from app.config import Settings
from app.main import app


def test_app_refuses_to_start_in_production_with_invalid_password():
    # Empty password in production
    with pytest.raises(RuntimeError, match="APP_PASSWORD"):
        Settings(ENV="production", APP_PASSWORD="")

    # Short password (< 12 chars) in production
    with pytest.raises(RuntimeError, match="APP_PASSWORD"):
        Settings(ENV="production", APP_PASSWORD="shortpass")

    # Valid password in production
    s = Settings(
        ENV="production",
        APP_PASSWORD="a_very_secure_long_password_123",
        SESSION_SECRET="a" * 32,
    )
    assert s.APP_PASSWORD == "a_very_secure_long_password_123"

    # In development, empty password is permitted
    dev_s = Settings(ENV="development", APP_PASSWORD="")
    assert dev_s.APP_PASSWORD == ""


@pytest.mark.asyncio
async def test_unauthenticated_endpoints_fail_closed():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Public health endpoints return 200 without leaking scheduler details
        res_live = await ac.get("/health/live")
        assert res_live.status_code == 200
        assert res_live.json() == {"status": "ok"}

        res_health = await ac.get("/health")
        assert res_health.status_code == 200
        assert res_health.json() == {"status": "ok"}
        assert "scheduler_running" not in res_health.json()

        res_ready = await ac.get("/health/ready")
        assert res_ready.status_code == 200
        assert res_ready.json() == {"status": "ready"}

        # Unauthenticated UI endpoints must return 303 redirect to /login
        ui_paths = ["/", "/settings", "/trace"]
        for p in ui_paths:
            res = await ac.get(p, follow_redirects=False)
            assert res.status_code == 303, f"Expected 303 for {p}, got {res.status_code}"
            assert res.headers["location"] == "/login"

        # Unauthenticated API endpoints must return 401 Unauthorized
        api_paths = ["/api/jobs", "/api/settings", "/api/trace/logs", "/api/health/detailed"]
        for p in api_paths:
            res = await ac.get(p)
            assert res.status_code == 401, f"Expected 401 for {p}, got {res.status_code}"
            assert "Unauthorized" in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_authenticated_detailed_health():
    from app.config import settings

    settings.APP_PASSWORD = "supersecretpassword123"
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {settings.APP_PASSWORD}"}

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/health/detailed", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert "scheduler_running" in data
        assert "scrape_interval_minutes" in data

