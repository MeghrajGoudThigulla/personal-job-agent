from datetime import timedelta, timezone
import os
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core import clock
from app.core.models import Base, JobPosting


def test_clock_helpers():
    now = clock.utcnow()
    assert now.tzinfo is not None
    assert now.tzinfo == timezone.utc

    ist_now = clock.to_ist(now)
    assert ist_now is not None
    # Asia/Kolkata is UTC+5:30 (19800 seconds)
    assert ist_now.utcoffset() == timedelta(seconds=19800)

    # Test naive datetime conversion
    naive = now.replace(tzinfo=None)
    ist_from_naive = clock.to_ist(naive)
    assert ist_from_naive.utcoffset() == timedelta(seconds=19800)

    formatted = clock.format_ist(now)
    assert "IST" in formatted


@pytest.mark.asyncio
async def test_aware_datetime_comparison_sqlite(tmp_path):
    db_path = tmp_path / "test_tz.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    now = clock.utcnow()
    old_time = now - timedelta(days=10)
    new_time = now - timedelta(days=2)
    cutoff = now - timedelta(days=5)

    async with session_factory() as session:
        j_old = JobPosting(
            title="Old Engineer",
            company="Legacy Corp",
            url="https://example.com/job/old",
            source_platform="test",
            discovered_at=old_time,
        )
        j_new = JobPosting(
            title="New Engineer",
            company="Modern Corp",
            url="https://example.com/job/new",
            source_platform="test",
            discovered_at=new_time,
        )
        session.add_all([j_old, j_new])
        await session.commit()

    async with session_factory() as session:
        # Query with aware cutoff
        stmt = select(JobPosting).where(JobPosting.discovered_at >= cutoff)
        res = await session.execute(stmt)
        results = res.scalars().all()

        assert len(results) == 1
        retrieved = results[0]
        assert retrieved.title == "New Engineer"
        # Verify retrieved datetime is aware and can be directly compared in python
        assert retrieved.discovered_at.tzinfo is not None
        assert retrieved.discovered_at >= cutoff

    await engine.dispose()


@pytest.mark.asyncio
async def test_aware_datetime_comparison_postgres():
    test_pg_url = os.getenv("TEST_DATABASE_URL")
    if not test_pg_url:
        pytest.skip("TEST_DATABASE_URL not set; skipping Postgres aware datetime test")

    from app.core.database import normalize_database_url

    pg_url = normalize_database_url(test_pg_url)
    engine = create_async_engine(pg_url)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    now = clock.utcnow()
    new_time = now - timedelta(days=1)
    cutoff = now - timedelta(days=3)

    async with session_factory() as session:
        j = JobPosting(
            title="PG Engineer",
            company="Postgres Corp",
            url="https://example.com/job/pg-test",
            source_platform="test",
            discovered_at=new_time,
        )
        session.add(j)
        await session.commit()

        stmt = select(JobPosting).where(JobPosting.discovered_at >= cutoff)
        res = await session.execute(stmt)
        results = res.scalars().all()
        assert any(r.company == "Postgres Corp" for r in results)

    await engine.dispose()

