import pytest
from app.config import settings
from app.scrapers.jobspy_scraper import JobSpyScraper


@pytest.mark.asyncio
async def test_jobspy_scraper_disabled(monkeypatch):
    monkeypatch.setattr(settings, "JOBSPY_ENABLED", False)
    scraper = JobSpyScraper()
    jobs = await scraper.scrape()
    assert jobs == []


@pytest.mark.asyncio
async def test_jobspy_scraper_cmd_construction(monkeypatch):
    captured_cmd = []

    async def mock_subprocess_exec(*cmd, **kwargs):
        nonlocal captured_cmd
        captured_cmd = list(cmd)

        class MockProcess:
            returncode = 0

            async def communicate(self):
                return (b"[]", b"")

        return MockProcess()

    monkeypatch.setattr(settings, "JOBSPY_ENABLED", True)
    monkeypatch.setattr(settings, "JOBSPY_SITES", "indeed,linkedin")
    monkeypatch.setattr(settings, "JOBSPY_PROXIES", "http://proxy1:8080,http://proxy2:8080")
    monkeypatch.setattr(settings, "JOBSPY_RESULTS_WANTED", 3)
    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_subprocess_exec)

    scraper = JobSpyScraper()
    jobs = await scraper.scrape()
    assert jobs == []

    cmd_str = " ".join(captured_cmd)
    assert "--results-wanted 3" in cmd_str
    assert "--sites indeed linkedin" in cmd_str
    assert "--proxies http://proxy1:8080 http://proxy2:8080" in cmd_str
    assert "--country india" in cmd_str
