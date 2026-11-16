import pytest
from httpx import AsyncClient, ASGITransport
from app.config import settings
from app.core.database import init_db, async_session_factory
from app.core.models import LinkedInPost
from app.main import app
from app.intelligence.linkedin_post_generator import (
    LinkedInPostGenerator,
    ENGINEERING_THEMES,
)

AUTH_HEADERS = {"Authorization": "Bearer supersecretpassword123"}


@pytest.fixture(autouse=True)
def configure_test_auth():
    settings.APP_PASSWORD = "supersecretpassword123"
    yield


@pytest.mark.asyncio
async def test_linkedin_post_generator_offline_generation():
    generator = LinkedInPostGenerator()
    post_data = await generator.generate_daily_post(theme_override="Backend Architecture")

    assert "Backend Architecture" in post_data["theme"]
    assert len(post_data["content"]) > 100
    assert "hashtags" in post_data
    assert len(post_data["hashtags"]) > 0
    assert post_data["is_clean"] is True
    assert post_data["slop_score"] <= 20.0

    # Ensure anti-slop checks pass
    content_lower = post_data["content"].lower()
    for buzzword in ["thrilled to announce", "game-changer", "delve into", "tapestry of"]:
        assert buzzword not in content_lower


@pytest.mark.asyncio
async def test_linkedin_post_theme_cycling():
    generator = LinkedInPostGenerator()
    seen_themes = set()
    from datetime import datetime, timezone, timedelta
    base_dt = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    for i in range(len(ENGINEERING_THEMES)):
        dt = base_dt + timedelta(days=i)
        theme = generator.get_todays_theme(target_date=dt)
        seen_themes.add(theme["theme"])
    assert len(seen_themes) == len(ENGINEERING_THEMES)


@pytest.mark.asyncio
async def test_linkedin_api_lifecycle():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Generate post via API
        gen_res = await ac.post(
            "/api/linkedin/generate",
            json={"theme_override": "Edge AI", "send_telegram": False},
            headers=AUTH_HEADERS,
        )
        assert gen_res.status_code == 200
        post = gen_res.json()
        assert "theme" in post
        post_id = post["id"]

        # 2. Query today's post
        today_res = await ac.get("/api/linkedin/today", headers=AUTH_HEADERS)
        assert today_res.status_code == 200
        today_data = today_res.json()
        assert today_data is not None
        assert today_data["id"] == post_id

        # 3. Query post list
        list_res = await ac.get("/api/linkedin/posts", headers=AUTH_HEADERS)
        assert list_res.status_code == 200
        posts = list_res.json()
        assert any(p["id"] == post_id for p in posts)

        # 4. Update status to posted
        patch_res = await ac.patch(
            f"/api/linkedin/posts/{post_id}/status",
            json={"posted": True},
            headers=AUTH_HEADERS,
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["posted"] is True

        # 5. Clean up post from database to keep test state clean
        async with async_session_factory() as session:
            db_post = await session.get(LinkedInPost, post_id)
            if db_post:
                await session.delete(db_post)
                await session.commit()
