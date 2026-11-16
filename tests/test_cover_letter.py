import httpx
import pytest
from app.intelligence.anti_slop import AntiSlopValidator
from app.intelligence.cover_letter import CoverLetterGenerator
from app.notifiers.telegram import TelegramNotifier


def test_cover_letter_fallback_generation():
    generator = CoverLetterGenerator()
    letter = generator.generate_fallback_text(
        job_title="Senior Python Backend Engineer",
        company="Razorpay",
        matched_skills=["Python", "FastAPI", "PostgreSQL", "Kafka"],
    )

    assert "Razorpay" in letter
    assert "Senior Python Backend Engineer" in letter
    assert "286 API endpoints" in letter
    assert "Thigulla Meghraj Goud" in letter
    assert "meghraj.thigulla@outlook.com" in letter

    validator = AntiSlopValidator()
    eval_res = validator.evaluate_text(letter)
    assert eval_res["is_clean"] is True
    assert eval_res["score"] <= 20.0
    assert eval_res["word_count"] < 220


@pytest.mark.asyncio
async def test_cover_letter_async_generate():
    generator = CoverLetterGenerator()
    letter = await generator.generate(
        job_title="Lead Platform Engineer",
        company="Swiggy",
        description="Scaling high-throughput services with Python, Go, and Redis.",
        matched_skills=["Python", "FastAPI", "Redis"],
    )

    assert "Swiggy" in letter
    assert "Lead Platform Engineer" in letter
    assert "Thigulla Meghraj Goud" in letter

    validator = AntiSlopValidator()
    eval_res = validator.evaluate_text(letter)
    assert eval_res["is_clean"] is True


@pytest.mark.asyncio
async def test_telegram_notifier_includes_copyable_cover_letter(monkeypatch):
    sent_payloads = []

    async def mock_post(self, url, **kwargs):
        sent_payloads.append(kwargs.get("json", {}))
        return httpx.Response(200, json={"ok": True}, request=httpx.Request("POST", url))

    monkeypatch.setattr("httpx.AsyncClient.post", mock_post)

    notifier = TelegramNotifier(bot_token="fake_bot_token", chat_id="12345678")

    job_data = {
        "id": 42,
        "title": "Backend Engineer",
        "company": "Cred",
        "location": "Bangalore",
        "match_score": 90.0,
        "match_tier": "P1",
        "role_category": "Engineering",
        "url": "https://cred.club/careers/1",
        "matched_skills": ["Python", "FastAPI"],
        "cover_letter": "Dear Cred Hiring Team,\n\nI am applying for Backend Engineer.\n\nSincerely,\nMeghraj",
    }

    res = await notifier.send_job_alert(job_data)
    assert res is True
    assert len(sent_payloads) == 1
    sent_text = sent_payloads[0].get("text", "")
    assert "Cred" in sent_text
    assert "Quick-Copy Cover Letter:" in sent_text
    assert "```Dear Cred Hiring Team," in sent_text
