import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from app.config import settings
from app.core.database import async_session_factory, engine, init_db
from app.core.models import JobPosting
from app.main import app
from app.notifiers.weekly_digest import WeeklyDigestNotifier

AUTH_HEADERS = {"Authorization": "Bearer supersecretpassword123"}


@pytest.fixture(autouse=True)
def configure_test_auth():
    settings.APP_PASSWORD = "supersecretpassword123"
    yield


@pytest.mark.asyncio
async def test_compile_and_format_weekly_digest():
    await init_db()

    uid = uuid.uuid4().hex[:6]
    async with async_session_factory() as db:
        j1 = JobPosting(
            title="Principal Platform Architect",
            company="Solana Systems",
            location="Remote, India",
            url=f"https://solana.example/jobs/{uid}-1",
            source_platform="Ashby",
            match_score=999.0,
            status="interviewing",
            interview_stage="Round 2 (System Design)",
            match_reason='{"matched_skills": ["Python", "Docker"], "missing_skills": ["Kubernetes", "Rust"]}'
        )
        j2 = JobPosting(
            title="Senior Backend Engineer",
            company="Stripe",
            location="Bangalore",
            url=f"https://stripe.example/jobs/{uid}-2",
            source_platform="LinkedIn",
            match_score=91.0,
            status="applied",
            match_reason='{"matched_skills": ["FastAPI", "Postgres"], "missing_skills": ["Kubernetes"]}'
        )
        db.add_all([j1, j2])
        await db.commit()

        notifier = WeeklyDigestNotifier()
        data = await notifier.compile_digest_data(db, days=7)
        assert data["discovered"] >= 2
        assert data["qualified"] >= 2
        assert data["applied"] >= 2
        assert data["interviewing"] >= 1
        assert len(data["top_jobs"]) >= 2
        assert data["top_jobs"][0]["title"] == "Principal Platform Architect"

        tg_text = notifier.format_telegram_digest(data)
        assert "WEEKLY JOB SEARCH & PIPELINE DIGEST" in tg_text
        assert "Solana Systems" in tg_text
        assert "Kubernetes" in tg_text

    await engine.dispose()


@pytest.mark.asyncio
async def test_weekly_digest_api_endpoints(monkeypatch):
    await init_db()

    # Mock telegram notifier send_message
    async def mock_send_message(*args, **kwargs):
        return True

    from app.notifiers.telegram import TelegramNotifier
    monkeypatch.setattr(TelegramNotifier, "is_configured", True)
    monkeypatch.setattr(TelegramNotifier, "send_message", mock_send_message)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Preview
        res_prev = await ac.get("/api/digest/preview", headers=AUTH_HEADERS)
        assert res_prev.status_code == 200
        data_prev = res_prev.json()
        assert "digest_summary" in data_prev
        assert "text" in data_prev
        assert "WEEKLY JOB SEARCH & PIPELINE DIGEST" in data_prev["text"]

        # 2. Trigger send
        res_send = await ac.post("/api/digest/send", headers=AUTH_HEADERS)
        assert res_send.status_code == 200
        data_send = res_send.json()
        assert data_send["success"] is True
        assert "telegram" in data_send["dispatched_channels"]

    await engine.dispose()
