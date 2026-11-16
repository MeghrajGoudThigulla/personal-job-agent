import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core import clock
from app.core.models import Base, JobPosting
from app.core.scheduler import scheduled_digest_task
from app.notifiers.dispatcher import NotificationDispatcher


@pytest.mark.asyncio
async def test_scheduled_digest_task_dispatches_alerts(tmp_path, monkeypatch):
    """Verifies scheduled_digest_task queries top jobs and dispatches alerts without AttributeError."""
    db_path = tmp_path / "test_digest.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    test_engine = create_async_engine(db_url)
    test_session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr("app.core.database.async_session_factory", test_session_factory)

    dispatched = []

    async def mock_dispatch_job_alert(self, job_data):
        dispatched.append(job_data)
        return True

    monkeypatch.setattr(NotificationDispatcher, "dispatch_job_alert", mock_dispatch_job_alert)

    # Insert jobs
    async with test_session_factory() as session:
        for i in range(3):
            session.add(
                JobPosting(
                    title=f"Engineer {i}",
                    company=f"Company {i}",
                    location="Hyderabad, India",
                    url=f"https://company.com/job/{i}",
                    source_platform="DirectATS",
                    match_score=85.0 + i,
                    discovered_at=clock.utcnow(),
                )
            )
        await session.commit()

    # Execute scheduled digest
    await scheduled_digest_task()

    assert len(dispatched) == 3
    assert dispatched[0]["title"] == "Engineer 2"  # ordered by discovered_at desc


@pytest.mark.asyncio
async def test_notification_dispatcher_notify_job_alias(monkeypatch):
    """Verifies notify_job acts as a backward-compatible alias for dispatch_job_alert."""
    dispatcher = NotificationDispatcher()
    called = []

    async def mock_dispatch(self, job_data):
        called.append(job_data)
        return True

    monkeypatch.setattr(NotificationDispatcher, "dispatch_job_alert", mock_dispatch)

    payload = {"title": "Backend Engineer", "match_score": 90.0}
    result = await dispatcher.notify_job(payload)
    assert result is True
    assert len(called) == 1
    assert called[0]["title"] == "Backend Engineer"
