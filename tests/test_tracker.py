import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import settings
from app.core.models import Base, JobPosting, InterviewRound
from app.core.security import create_session
from app.main import app


@pytest.fixture
async def tracker_env(tmp_path, monkeypatch):
    db_path = tmp_path / "test_tracker.db"
    test_db_url = f"sqlite+aiosqlite:///{db_path}"
    test_engine = create_async_engine(test_db_url)
    test_session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr("app.core.database.async_session_factory", test_session_factory)
    monkeypatch.setattr("app.main.async_session_factory", test_session_factory)

    async def override_get_db():
        async with test_session_factory() as session:
            yield session

    from app.core.database import get_db
    app.dependency_overrides[get_db] = override_get_db

    # Create an authenticated session
    async with test_session_factory() as db:
        session_rec, cookie_val = await create_session(db, client_ip="127.0.0.1")

    cookies = {settings.ADMIN_SESSION_COOKIE: cookie_val}
    headers = {"X-CSRF-Token": session_rec.csrf_token}

    yield {
        "session_factory": test_session_factory,
        "cookies": cookies,
        "headers": headers,
    }

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_tracker_kanban_partitioning(tracker_env):
    session_factory = tracker_env["session_factory"]
    cookies = tracker_env["cookies"]

    async with session_factory() as session:
        j1 = JobPosting(title="Dev 1", company="A", url="https://a.com/1", source_platform="Web", status="new")
        j2 = JobPosting(title="Dev 2", company="B", url="https://b.com/2", source_platform="Web", status="applied")
        j3 = JobPosting(title="Dev 3", company="C", url="https://c.com/3", source_platform="Web", status="interviewing")
        j4 = JobPosting(title="Dev 4", company="D", url="https://d.com/4", source_platform="Web", status="offer")
        j5 = JobPosting(title="Dev 5", company="E", url="https://e.com/5", source_platform="Web", status="rejected")
        session.add_all([j1, j2, j3, j4, j5])
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", cookies=cookies) as client:
        res = await client.get("/api/tracker/kanban")
        assert res.status_code == 200
        board = res.json()
        assert len(board["discovered"]) == 1
        assert len(board["applied"]) == 1
        assert len(board["interviewing"]) == 1
        assert len(board["offer"]) == 1
        assert len(board["rejected"]) == 1


@pytest.mark.asyncio
async def test_update_status_and_applied_at(tracker_env):
    session_factory = tracker_env["session_factory"]
    cookies = tracker_env["cookies"]
    headers = tracker_env["headers"]

    async with session_factory() as session:
        j = JobPosting(title="Software Engineer", company="Linear", url="https://linear.app/1", source_platform="Web", status="new")
        session.add(j)
        await session.commit()
        await session.refresh(j)
        job_id = j.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", cookies=cookies) as client:
        res = await client.post(
            "/api/tracker/status",
            json={"job_id": job_id, "status": "applied", "notes": "Submitted referral"},
            headers=headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["new_status"] == "applied"
        assert data["applied_at"] is not None

    async with session_factory() as session:
        updated = await session.get(JobPosting, job_id)
        assert updated.status == "applied"
        assert updated.applied_at is not None
        assert updated.notes == "Submitted referral"


@pytest.mark.asyncio
async def test_interview_rounds_lifecycle(tracker_env):
    session_factory = tracker_env["session_factory"]
    cookies = tracker_env["cookies"]
    headers = tracker_env["headers"]

    async with session_factory() as session:
        j = JobPosting(title="Staff Engineer", company="PostHog", url="https://posthog.com/1", source_platform="Web", status="applied")
        session.add(j)
        await session.commit()
        await session.refresh(j)
        job_id = j.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", cookies=cookies) as client:
        # Create interview round
        res = await client.post(
            "/api/tracker/interview",
            json={
                "job_id": job_id,
                "round_number": 1,
                "round_type": "technical",
                "interviewer_name": "Alex",
                "outcome": "passed",
                "notes": "System design deep dive on Postgres partitioning",
            },
            headers=headers,
        )
        assert res.status_code == 200
        round_data = res.json()["interview_round"]
        assert round_data["round_type"] == "technical"
        assert round_data["interviewer_name"] == "Alex"
        round_id = round_data["id"]

        # Check stats endpoint
        stats_res = await client.get("/api/tracker/stats")
        assert stats_res.status_code == 200
        stats = stats_res.json()
        assert stats["total_interviewing"] == 1

        # Delete interview round
        del_res = await client.delete(f"/api/tracker/interview/{round_id}", headers=headers)
        assert del_res.status_code == 200
        assert del_res.json()["deleted_round_id"] == round_id

    async with session_factory() as session:
        remaining = await session.get(InterviewRound, round_id)
        assert remaining is None


@pytest.mark.asyncio
async def test_tracker_html_view(tracker_env):
    cookies = tracker_env["cookies"]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", cookies=cookies) as client:
        res = await client.get("/tracker")
        assert res.status_code == 200
        assert "Application Kanban" in res.text
