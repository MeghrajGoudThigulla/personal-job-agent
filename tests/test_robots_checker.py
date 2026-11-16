import pytest
from app.scrapers.robots_checker import RobotsChecker


@pytest.mark.asyncio
async def test_robots_checker_allow_and_disallow(monkeypatch):
    checker = RobotsChecker()

    robots_content = """
User-agent: *
Disallow: /admin/
Disallow: /private/jobs/
Allow: /jobs/
Crawl-delay: 2
"""

    class MockResponse:
        status_code = 200
        text = robots_content

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, *args, **kwargs):
            return MockResponse()

    monkeypatch.setattr("httpx.AsyncClient", MockClient)

    # 1. Allowed path
    allowed = await checker.is_allowed("https://careers.example.com/jobs/senior-dev")
    assert allowed is True

    # 2. Disallowed path
    disallowed = await checker.is_allowed("https://careers.example.com/private/jobs/secret")
    assert disallowed is False

    # 3. Crawl delay
    delay = await checker.get_crawl_delay("https://careers.example.com/jobs/senior-dev")
    assert delay == 2.0


@pytest.mark.asyncio
async def test_robots_checker_fails_open_on_error(monkeypatch):
    checker = RobotsChecker()

    class BrokenClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, *args, **kwargs):
            raise RuntimeError("Connection refused")

    monkeypatch.setattr("httpx.AsyncClient", BrokenClient)

    # On error, RFC 9309 compliance demands fail-open
    allowed = await checker.is_allowed("https://unreachable.example.com/jobs/python-dev")
    assert allowed is True


@pytest.mark.asyncio
async def test_robots_checker_cache_reuse(monkeypatch):
    checker = RobotsChecker()
    fetch_count = 0

    class CountingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, *args, **kwargs):
            nonlocal fetch_count
            fetch_count += 1
            class Res:
                status_code = 200
                text = "User-agent: *\nAllow: /"
            return Res()

    monkeypatch.setattr("httpx.AsyncClient", CountingClient)

    # First call fetches robots.txt
    await checker.is_allowed("https://cached.example.com/jobs/1")
    assert fetch_count == 1

    # Second call for same domain should use cache
    await checker.is_allowed("https://cached.example.com/jobs/2")
    assert fetch_count == 1
