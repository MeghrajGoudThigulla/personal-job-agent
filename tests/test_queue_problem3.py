from datetime import timedelta
from unittest.mock import AsyncMock
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core import clock
from app.core.fingerprint import compute_fingerprint
from app.core.models import Base, JobPosting
from app.main import app
from app.scrapers.engine import ScraperEngine


@pytest.fixture(autouse=True)
def speed_up_asyncio_sleep(monkeypatch):
    """Bypasses pacing sleeps during unit testing so the test suite finishes instantly."""
    async def fast_sleep(*args, **kwargs):
        return None

    monkeypatch.setattr("asyncio.sleep", fast_sleep)
    monkeypatch.setattr(
        "app.intelligence.cover_letter.CoverLetterGenerator.generate",
        AsyncMock(return_value="Mocked cover letter"),
    )


@pytest.mark.asyncio
async def test_failing_notification_does_not_block_and_stops_at_max(tmp_path, monkeypatch):
    db_path = tmp_path / "test_hol.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    test_engine = create_async_engine(db_url)
    test_session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr("app.scrapers.engine.async_session_factory", test_session_factory)
    monkeypatch.setattr("app.config.settings.AUTO_TAILOR_HIGH_MATCH", False)

    engine = ScraperEngine()
    monkeypatch.setattr(
        "app.notifiers.dispatcher.NotificationDispatcher.is_any_configured",
        property(lambda self: True),
    )

    now = clock.utcnow()
    # Insert Job 1 (score 95, failing notifier) and Job 2 (score 90, successful notifier)
    async with test_session_factory() as session:
        j1 = JobPosting(
            title="Senior Dev (Failing Notification)",
            company="FailCorp",
            location="Hyderabad",
            url="https://failcorp.com/1",
            source_platform="Web",
            match_score=95.0,
            notified=False,
            notify_attempts=0,
            discovered_at=now,
            posted_at=now,
            fingerprint=compute_fingerprint("FailCorp", "Senior Dev (Failing Notification)", "Hyderabad"),
        )
        j2 = JobPosting(
            title="Senior Dev (Succeeding Notification)",
            company="PassCorp",
            location="Hyderabad",
            url="https://passcorp.com/2",
            source_platform="Web",
            match_score=90.0,
            notified=False,
            notify_attempts=0,
            discovered_at=now,
            posted_at=now,
            fingerprint=compute_fingerprint("PassCorp", "Senior Dev (Succeeding Notification)", "Hyderabad"),
        )
        session.add_all([j1, j2])
        await session.commit()

    engine.scrapers = []

    # Mock dispatch: fails for FailCorp, succeeds for PassCorp
    async def mock_dispatch(payload):
        return "PassCorp" in payload.get("company", "")

    monkeypatch.setattr(engine.notifier, "dispatch_job_alert", mock_dispatch)

    # Cycle 1
    await engine.run_discovery_cycle()

    async with test_session_factory() as session:
        res1 = await session.execute(select(JobPosting).where(JobPosting.company == "FailCorp"))
        fail_job = res1.scalar_one()
        assert fail_job.notified is False
        assert fail_job.notify_attempts == 1
        assert fail_job.next_attempt_at is not None
        assert fail_job.next_attempt_at > now
        assert fail_job.last_error is not None

        res2 = await session.execute(select(JobPosting).where(JobPosting.company == "PassCorp"))
        pass_job = res2.scalar_one()
        # Crucial: FailCorp did NOT block PassCorp! PassCorp was notified!
        assert pass_job.notified is True
        assert pass_job.notified_at is not None

    # Now simulate subsequent cycles for FailCorp by advancing time
    for expected_attempt in range(2, 6):
        async with test_session_factory() as session:
            j = (await session.execute(select(JobPosting).where(JobPosting.company == "FailCorp"))).scalar_one()
            j.next_attempt_at = clock.utcnow() - timedelta(minutes=1)
            await session.commit()

        await engine.run_discovery_cycle()

        async with test_session_factory() as session:
            j = (await session.execute(select(JobPosting).where(JobPosting.company == "FailCorp"))).scalar_one()
            assert j.notify_attempts == expected_attempt

    # 6th attempt: FailCorp has reached MAX_NOTIFY_ATTEMPTS (5), so it must NOT be retried again
    async with test_session_factory() as session:
        j = (await session.execute(select(JobPosting).where(JobPosting.company == "FailCorp"))).scalar_one()
        assert j.notify_attempts == settings.MAX_NOTIFY_ATTEMPTS
        j.next_attempt_at = clock.utcnow() - timedelta(minutes=1)
        await session.commit()

    await engine.run_discovery_cycle()

    async with test_session_factory() as session:
        j = (await session.execute(select(JobPosting).where(JobPosting.company == "FailCorp"))).scalar_one()
        assert j.notify_attempts == settings.MAX_NOTIFY_ATTEMPTS

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_twelve_qualifying_jobs_notified_across_three_cycles(tmp_path, monkeypatch):
    db_path = tmp_path / "test_12_jobs.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    test_engine = create_async_engine(db_url)
    test_session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr("app.scrapers.engine.async_session_factory", test_session_factory)
    monkeypatch.setattr("app.config.settings.AUTO_TAILOR_HIGH_MATCH", False)

    engine = ScraperEngine()
    engine.scrapers = []
    monkeypatch.setattr(
        "app.notifiers.dispatcher.NotificationDispatcher.is_any_configured",
        property(lambda self: True),
    )

    async def mock_dispatch(payload):
        return True

    monkeypatch.setattr(engine.notifier, "dispatch_job_alert", mock_dispatch)

    now = clock.utcnow()
    # Insert 12 qualifying jobs
    async with test_session_factory() as session:
        jobs = []
        for i in range(12):
            jobs.append(
                JobPosting(
                    title=f"Engineer {i}",
                    company=f"Company {i}",
                    location="Hyderabad",
                    url=f"https://company{i}.com/job",
                    source_platform="Web",
                    match_score=80.0 + i,
                    notified=False,
                    notify_attempts=0,
                    discovered_at=now - timedelta(minutes=i),
                    posted_at=now,
                    fingerprint=compute_fingerprint(f"Company {i}", f"Engineer {i}", "Hyderabad"),
                )
            )
        session.add_all(jobs)
        await session.commit()

    # Cycle 1: should notify top 5
    stats1 = await engine.run_discovery_cycle()
    assert stats1["notified_count"] == 5

    # Cycle 2: should notify next 5
    stats2 = await engine.run_discovery_cycle()
    assert stats2["notified_count"] == 5

    # Cycle 3: should notify remaining 2
    stats3 = await engine.run_discovery_cycle()
    assert stats3["notified_count"] == 2

    # Verify all 12 are notified
    async with test_session_factory() as session:
        res = await session.execute(select(JobPosting).where(JobPosting.notified == True))
        notified_jobs = res.scalars().all()
        assert len(notified_jobs) == 12

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_tailoring_runs_once_even_when_notification_fails(tmp_path, monkeypatch):
    db_path = tmp_path / "test_tailor_once.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    test_engine = create_async_engine(db_url)
    test_session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr("app.scrapers.engine.async_session_factory", test_session_factory)
    monkeypatch.setattr("app.config.settings.AUTO_TAILOR_HIGH_MATCH", True)

    engine = ScraperEngine()
    engine.scrapers = []
    monkeypatch.setattr(
        "app.notifiers.dispatcher.NotificationDispatcher.is_any_configured",
        property(lambda self: True),
    )

    async def mock_failing_dispatch(payload):
        return False

    monkeypatch.setattr(engine.notifier, "dispatch_job_alert", mock_failing_dispatch)

    tailor_call_count = 0

    async def mock_tailor(**kwargs):
        nonlocal tailor_call_count
        tailor_call_count += 1
        return {
            "tailored_tex": "\\documentclass{article}\\begin{document}Resume\\end{document}",
            "tailored_md": "# Resume",
            "slop_score": 0.0,
        }

    monkeypatch.setattr(engine.tailor, "tailor_resume", mock_tailor)
    monkeypatch.setattr(engine.pdf_compiler, "compile_resume", lambda **kwargs: {"pdf_path": ""})
    monkeypatch.setattr(
        engine.outreach,
        "generate_outreach",
        lambda **kwargs: {
            "hr_email": {"body": "hi"},
            "hiring_manager_email": {"body": "hello"},
            "linkedin_4mm": ["msg1"],
        },
    )
    monkeypatch.setattr(
        engine.cover_letter_gen,
        "generate",
        AsyncMock(return_value="Mocked cover letter"),
    )

    now = clock.utcnow()
    async with test_session_factory() as session:
        j = JobPosting(
            title="Python Dev",
            company="Startup",
            location="Hyderabad",
            url="https://startup.io/job",
            source_platform="Web",
            match_score=90.0,
            notified=False,
            notify_attempts=0,
            tailor_status="pending",
            discovered_at=now,
            posted_at=now,
            fingerprint=compute_fingerprint("Startup", "Python Dev", "Hyderabad"),
        )
        session.add(j)
        await session.commit()

    # Cycle 1: notification fails, but tailoring runs
    await engine.run_discovery_cycle()
    assert tailor_call_count == 1

    async with test_session_factory() as session:
        j = (await session.execute(select(JobPosting))).scalar_one()
        assert j.notified is False
        assert j.tailor_status == "done"
        assert j.status == "tailored"

        # Simulate retry window arrived
        j.next_attempt_at = clock.utcnow() - timedelta(minutes=1)
        await session.commit()

    # Cycle 2: notification retries, but tailoring must NOT re-run!
    await engine.run_discovery_cycle()
    assert tailor_call_count == 1 # Tailoring was NOT called again!

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_manual_retry_endpoint(tmp_path, monkeypatch):
    db_path = tmp_path / "test_retry_api.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    test_engine = create_async_engine(db_url)
    test_session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from app.core import database
    monkeypatch.setattr(database, "async_session_factory", test_session_factory)

    async def override_get_db():
        async with test_session_factory() as session:
            yield session

    from app.core.database import get_db
    app.dependency_overrides[get_db] = override_get_db

    monkeypatch.setattr(settings, "ENV", "development")
    monkeypatch.setattr(settings, "APP_PASSWORD", "testpassword123")

    now = clock.utcnow()
    async with test_session_factory() as session:
        j = JobPosting(
            title="Job to Retry",
            company="RetryCorp",
            location="Hyderabad",
            url="https://retry.io/job",
            source_platform="Web",
            match_score=92.0,
            notified=False,
            notify_attempts=5,
            next_attempt_at=now + timedelta(hours=1),
            last_error="Simulated failure",
            tailor_status="failed",
            discovered_at=now,
            posted_at=now,
        )
        session.add(j)
        await session.commit()
        job_id = j.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Call with Bearer auth
        res = await client.post(
            f"/api/jobs/{job_id}/retry",
            headers={"Authorization": "Bearer testpassword123"}
        )
        assert res.status_code == 200
        assert res.json()["status"] == "reset_for_retry"

    async with test_session_factory() as session:
        updated = await session.get(JobPosting, job_id)
        assert updated.notify_attempts == 0
        assert updated.next_attempt_at is None
        assert updated.last_error is None
        assert updated.tailor_status == "pending"

    app.dependency_overrides.clear()
    await test_engine.dispose()
