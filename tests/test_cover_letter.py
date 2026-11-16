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
        "tailored_tex": "\\documentclass{article}\n\\begin{document}\nMeghraj Goud Resume\n\\end{document}",
    }

    res = await notifier.send_job_alert(job_data)
    assert res is True
    # Message 1: Job Alert, Message 2: Cover Letter, Message 3: Tailored Resume LaTeX
    assert len(sent_payloads) == 3

    # 1. Job Alert Message
    job_msg = sent_payloads[0].get("text", "")
    assert "NEW HIGH-MATCH JOB DISCOVERED" in job_msg
    assert "Cred" in job_msg
    assert "Backend Engineer" in job_msg
    assert "https://cred.club/careers/1" in job_msg

    # 2. Subsequent Cover Letter Message
    cl_msg = sent_payloads[1].get("text", "")
    assert "Tailored Cover Letter" in cl_msg
    assert "Dear Cred Hiring Team," in cl_msg

    # 3. Subsequent Tailored Resume LaTeX Message
    latex_msg = sent_payloads[2].get("text", "")
    assert "Tailored Resume LaTeX" in latex_msg
    assert "\\documentclass{article}" in latex_msg
    assert "Meghraj Goud Resume" in latex_msg


@pytest.mark.asyncio
async def test_telegram_notifier_chunks_large_latex_code(monkeypatch):
    sent_payloads = []

    async def mock_post(self, url, **kwargs):
        sent_payloads.append(kwargs.get("json", {}))
        return httpx.Response(200, json={"ok": True}, request=httpx.Request("POST", url))

    monkeypatch.setattr("httpx.AsyncClient.post", mock_post)

    notifier = TelegramNotifier(bot_token="fake_bot_token", chat_id="12345678")

    # Generate a large 5000 character LaTeX string
    large_latex = "% LaTeX Header\n" + ("\\textbf{Skill Bullet Point with metrics}%\n" * 120)

    job_data = {
        "id": 99,
        "title": "Staff Platform Engineer",
        "company": "Zepto",
        "location": "Bangalore",
        "match_score": 95.0,
        "match_tier": "P1",
        "url": "https://zepto.com/careers/99",
        "tailored_tex": large_latex,
    }

    res = await notifier.send_job_alert(job_data)
    assert res is True
    # Message 1: Job alert, Message 2: LaTeX Part 1, Message 3: LaTeX Part 2
    assert len(sent_payloads) >= 3
    assert "Part 1/" in sent_payloads[1].get("text", "")
    assert "Part 2/" in sent_payloads[2].get("text", "")
