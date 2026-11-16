import httpx
import pytest
from app.intelligence.liveness import (
    CLOSED,
    OPEN,
    UNCLEAR,
    check_liveness,
    classify_response,
    posting_is_closed,
    get_ats_provider,
    workday_api_url,
    bamboohr_api_url,
    greenhouse_api_url,
)


def test_provider_detection():
    assert get_ats_provider("https://jobs.lever.co/stripe/abc") == "lever"
    assert get_ats_provider("https://jobs.ashbyhq.com/linear/xyz") == "ashby"
    assert get_ats_provider("https://boards.greenhouse.io/openai/jobs/123") == "greenhouse"
    assert get_ats_provider("https://apply.workable.com/post/123") == "workable"
    assert get_ats_provider("https://acme.bamboohr.com/careers/456") == "bamboohr"
    assert get_ats_provider("https://recruiting.paylocity.com/recruiting/jobs/details/789") == "paylocity"
    assert get_ats_provider("https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/USA/Engineer_123") == "workday"
    assert get_ats_provider("https://randomcompany.com/careers") is None


def test_api_url_converters():
    wd_url = "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/USA/Engineer_123"
    assert workday_api_url(wd_url) == "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/job/USA/Engineer_123"

    bb_url = "https://acme.bamboohr.com/careers/456"
    assert bamboohr_api_url(bb_url) == "https://acme.bamboohr.com/careers/456/detail"

    gh_url = "https://boards.greenhouse.io/openai/jobs/123"
    assert greenhouse_api_url(gh_url) == "https://boards-api.greenhouse.io/v1/boards/openai/jobs/123"


def test_classify_response_direct():
    assert classify_response("lever", 404, "https://jobs.lever.co/acme/1", "") == CLOSED
    assert classify_response("lever", 200, "https://jobs.lever.co/acme/1", "") == OPEN
    assert classify_response("workable", 200, "https://apply.workable.com/oops", "") == CLOSED
    assert classify_response("paylocity", 200, "https://recruiting.paylocity.com/recruiting/jobs/jobnotfound", "") == CLOSED
    assert classify_response("bamboohr", 404, "https://acme.bamboohr.com/careers/1/detail", "") == CLOSED
    assert classify_response("greenhouse", 200, "https://job-boards.greenhouse.io/acme?error=true", "") == CLOSED


@pytest.mark.asyncio
async def test_lever_liveness():
    handler = httpx.MockTransport(lambda req: httpx.Response(404))
    async with httpx.AsyncClient(transport=handler) as client:
        assert await check_liveness("https://jobs.lever.co/stripe/nonexistent", client=client) == CLOSED
        assert await posting_is_closed("https://jobs.lever.co/stripe/nonexistent", client=client) is True

    handler = httpx.MockTransport(lambda req: httpx.Response(200, text="Software Engineer at Stripe"))
    async with httpx.AsyncClient(transport=handler) as client:
        assert await check_liveness("https://jobs.lever.co/stripe/livejob", client=client) == OPEN
        assert await posting_is_closed("https://jobs.lever.co/stripe/livejob", client=client) is False


@pytest.mark.asyncio
async def test_ashby_liveness():
    handler = httpx.MockTransport(lambda req: httpx.Response(404, text="<html><head><title>Jobs</title></head><body>No posting</body></html>"))
    async with httpx.AsyncClient(transport=handler) as client:
        assert await check_liveness("https://jobs.ashbyhq.com/linear/abc", client=client) == CLOSED

    handler = httpx.MockTransport(lambda req: httpx.Response(404, text="<html><head><title>Server Error</title></head></html>"))
    async with httpx.AsyncClient(transport=handler) as client:
        assert await check_liveness("https://jobs.ashbyhq.com/linear/abc", client=client) == UNCLEAR


@pytest.mark.asyncio
async def test_greenhouse_redirect_and_api():
    def handle_request(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/company/jobs/123":
            return httpx.Response(302, headers={"location": "https://job-boards.greenhouse.io/company?error=true"})
        if "error=true" in str(request.url):
            return httpx.Response(200, text="<html>Board</html>")
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle_request), follow_redirects=True) as client:
        assert await check_liveness("https://boards.greenhouse.io/company/jobs/123", client=client) == CLOSED
        assert await posting_is_closed("https://boards.greenhouse.io/company/jobs/123", client=client) is True


@pytest.mark.asyncio
async def test_workday_closed_s22():
    s22_json = '{"errorCode": "S22", "message": "Job posting is no longer active"}'
    handler = httpx.MockTransport(lambda req: httpx.Response(403, text=s22_json))
    async with httpx.AsyncClient(transport=handler) as client:
        url = "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/USA/Engineer_123"
        assert await check_liveness(url, client=client) == CLOSED
        assert await posting_is_closed(url, client=client) is True


@pytest.mark.asyncio
async def test_unsupported_or_timeout_fails_safe():
    assert await check_liveness("https://unknowncompany.com/jobs/123") == UNCLEAR
    assert await posting_is_closed("https://unknowncompany.com/jobs/123") is False


@pytest.mark.asyncio
async def test_engine_skips_closed_posting(tmp_path, monkeypatch):
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from app.core.models import Base, JobPosting
    from app.scrapers.engine import ScraperEngine

    db_path = tmp_path / "test_liveness_engine.db"
    test_db_url = f"sqlite+aiosqlite:///{db_path}"
    test_engine = create_async_engine(test_db_url)
    test_session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr("app.scrapers.engine.async_session_factory", test_session_factory)
    monkeypatch.setattr("app.config.settings.AUTO_TAILOR_HIGH_MATCH", False)

    # Insert a high-match job
    async with test_session_factory() as session:
        job = JobPosting(
            title="Senior Python Engineer",
            company="Stripe",
            location="Remote",
            url="https://jobs.lever.co/stripe/closed-job-123",
            source_platform="Lever",
            match_score=95.0,
            status="new",
            notified=False,
        )
        session.add(job)
        await session.commit()

    # Mock posting_is_closed to return True for this URL
    async def mock_posting_is_closed(url, client=None):
        return "closed-job" in url

    monkeypatch.setattr("app.scrapers.engine.posting_is_closed", mock_posting_is_closed)

    engine = ScraperEngine()
    # Stub scapers list to empty so only Phase 2 runs
    engine.scrapers = []
    res = await engine.run_discovery_cycle()

    assert res["notified_count"] == 0

    async with test_session_factory() as session:
        from sqlalchemy import select
        j = (await session.execute(select(JobPosting))).scalar_one()
        assert j.status == "closed"
        assert j.notified is True
        assert "liveness check" in (j.last_error or "")

