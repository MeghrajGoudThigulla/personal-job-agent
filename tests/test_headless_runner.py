import pytest
from app.core.database import init_db
from scripts.run_headless_cycle import (
    run_linkedin_step,
    run_email_step,
    print_stats_summary,
)


@pytest.mark.asyncio
async def test_headless_linkedin_step():
    await init_db()
    # Force run LinkedIn step
    await run_linkedin_step(force=True)


@pytest.mark.asyncio
async def test_headless_email_step_noop():
    await init_db()
    # When credentials not configured, skips gracefully without error
    await run_email_step()


@pytest.mark.asyncio
async def test_headless_print_stats():
    await init_db()
    # Verify stats summary runs and logs without crashing
    await print_stats_summary()
