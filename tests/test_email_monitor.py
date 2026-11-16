import pytest
from app.email_monitor.summarizer import EmailSummarizer
from app.email_monitor.inbox_scanner import InboxScanner
from app.core.models import Base, SeenEmail
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker


def test_classify_interview_invitation():
    subject = "Interview Invitation: Senior Python Engineer at Uber"
    body = (
        "Hi Meghraj,\n\nWe were impressed by your profile and would love to invite you "
        "to a 45-minute technical round.\n"
        "Please pick a time on Calendly: https://calendly.com/uber-recruiting/tech-screen\n"
        "Alternatively, here is the Google Meet link: https://meet.google.com/abc-defg-hij\n"
    )
    res = EmailSummarizer.classify(subject, body)
    assert res["category"] == "INTERVIEW_INVITE"
    assert res["urgency"] == "HIGH"
    assert "https://meet.google.com/abc-defg-hij" in res["meeting_links"] or "https://calendly.com/uber-recruiting/tech-screen" in res["meeting_links"]


def test_classify_coding_assessment():
    subject = "Atlassian Online Assessment Invitation"
    body = (
        "Dear Candidate,\n\nYou have been invited to complete a HackerRank coding challenge. "
        "Please access the test here: https://www.hackerrank.com/tests/atlassian-backend-test\n"
        "You have 48 hours to complete this assessment.\n"
    )
    res = EmailSummarizer.classify(subject, body)
    assert res["category"] == "ASSESSMENT_TEST"
    assert res["urgency"] == "HIGH"
    assert any("hackerrank.com" in link for link in res["test_links"])


def test_classify_job_offer():
    subject = "Offer Letter from Razorpay"
    body = "Dear Meghraj,\nWe are pleased to offer you the position of Senior Backend Engineer at Razorpay."
    res = EmailSummarizer.classify(subject, body)
    assert res["category"] == "OFFER"
    assert res["urgency"] == "HIGH"


def test_classify_rejection():
    subject = "Update on your application at Stripe"
    body = "Thank you for taking the time to interview. Unfortunately, we have decided to pursue other candidates."
    res = EmailSummarizer.classify(subject, body)
    assert res["category"] == "REJECTION"
    assert res["urgency"] == "NORMAL"


def test_format_telegram_alert():
    classification = {
        "category": "INTERVIEW_INVITE",
        "urgency": "HIGH",
        "badge": "🚨 INTERVIEW INVITATION",
        "meeting_links": ["https://meet.google.com/xyz-123"],
        "test_links": [],
        "snippet": "We would love to invite you to a technical screen.",
    }
    alert = EmailSummarizer.format_telegram_alert(
        account="Gmail",
        sender="recruiting@google.com",
        subject="Google Interview",
        date_str="2026-11-16",
        classification=classification,
    )
    assert "INTERVIEW INVITATION" in alert
    assert "Gmail" in alert
    assert "recruiting@google.com" in alert
    assert "https://meet.google.com/xyz-123" in alert


@pytest.mark.asyncio
async def test_inbox_scanner_deduplication_and_alerting(tmp_path, monkeypatch):
    db_path = tmp_path / "test_email_scanner.db"
    test_db_url = f"sqlite+aiosqlite:///{db_path}"
    test_engine = create_async_engine(test_db_url)
    test_session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr("app.email_monitor.inbox_scanner.async_session_factory", test_session_factory)
    monkeypatch.setattr("app.config.settings.GMAIL_USER", "user@gmail.com")
    monkeypatch.setattr("app.config.settings.GMAIL_APP_PASSWORD", "secret123")

    sent_messages = []

    class MockTelegramNotifier:
        is_configured = True

        async def send_message(self, text, parse_mode="Markdown"):
            sent_messages.append(text)
            return True

    scanner = InboxScanner(notifier=MockTelegramNotifier())

    # Mock _scan_imap_sync to return a sample interview email
    def mock_imap_sync(account_name, host, port, user, app_password, seen_ids):
        if "msg_123" in seen_ids:
            return []
        return [{
            "message_id": "msg_123",
            "account": account_name,
            "sender": "hr@amazon.com",
            "subject": "Interview with Amazon",
            "date": "Mon, 16 Nov 2026 10:00:00 +0530",
            "body": "Hi Meghraj, your interview is scheduled at https://meet.google.com/amz-screen",
            "classification": EmailSummarizer.classify("Interview with Amazon", "scheduled at https://meet.google.com/amz-screen"),
        }]

    monkeypatch.setattr(scanner, "_scan_imap_sync", mock_imap_sync)

    # First scan -> 1 new email found & notified
    summary1 = await scanner.scan_all_accounts()
    assert summary1["new_emails_found"] == 1
    assert summary1["notified_count"] == 1
    assert len(sent_messages) == 1
    assert "Amazon" in sent_messages[0]

    # Verify SeenEmail persisted in DB
    async with test_session_factory() as session:
        from sqlalchemy import select
        records = (await session.execute(select(SeenEmail))).scalars().all()
        assert len(records) == 1
        assert records[0].message_id == "msg_123"

    # Second scan -> deduplicated, 0 new emails notified
    summary2 = await scanner.scan_all_accounts()
    assert summary2["new_emails_found"] == 0
    assert summary2["notified_count"] == 0
    assert len(sent_messages) == 1
