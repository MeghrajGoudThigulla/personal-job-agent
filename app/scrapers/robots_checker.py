"""
Robots.txt Scraping Compliance and Polite Crawling Engine.
Parses and caches robots.txt rules (RFC 9309) across target career domains and ATS portals
to prevent IP rate-limiting, observe Crawl-delay, and ensure ethical discovery scraping.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import httpx

logger = logging.getLogger("personal_job_agent.scrapers.robots_checker")

DEFAULT_USER_AGENT = "PersonalJobAgent/1.0"
CACHE_TTL = timedelta(hours=24)


class RobotsChecker:
    """
    In-memory cached robots.txt compliance checker.
    """

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
        # Domain -> (RobotFileParser, expiry_datetime)
        self._cache: Dict[str, Tuple[RobotFileParser, datetime]] = {}
        self._lock = asyncio.Lock()

    def get_domain(self, url: str) -> Optional[str]:
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return None

    async def get_parser_for_domain(self, domain: str) -> RobotFileParser:
        """
        Retrieves or fetches the RobotFileParser for a domain with a 24-hour cache.
        """
        now = datetime.now(timezone.utc)

        async with self._lock:
            if domain in self._cache:
                parser, expiry = self._cache[domain]
                if now < expiry:
                    return parser

        # Fetch robots.txt
        parser = RobotFileParser()
        robots_url = f"https://{domain}/robots.txt"

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                res = await client.get(robots_url, headers={"User-Agent": DEFAULT_USER_AGENT})
                if res.status_code == 200:
                    parser.parse(res.text.splitlines())
                else:
                    # RFC 9309: A 4xx status code (other than 429) indicates full access allowed.
                    parser.parse(["User-agent: *", "Allow: /"])
        except Exception as e:
            logger.debug(f"Unable to fetch robots.txt for {domain} ({e}), failing open.")
            parser.parse(["User-agent: *", "Allow: /"])

        async with self._lock:
            self._cache[domain] = (parser, now + CACHE_TTL)

        return parser

    async def is_allowed(self, url: str, user_agent: str = DEFAULT_USER_AGENT) -> bool:
        """
        Checks whether the specified URL is permissible to scrape under robots.txt.
        """
        domain = self.get_domain(url)
        if not domain:
            return True

        try:
            parser = await self.get_parser_for_domain(domain)
            allowed = parser.can_fetch(user_agent, url)
            if not allowed:
                # Also check wildcard user-agent
                allowed = parser.can_fetch("*", url)
            return bool(allowed)
        except Exception as e:
            logger.debug(f"Error checking robots.txt for {url}: {e}")
            return True

    async def get_crawl_delay(self, url: str, user_agent: str = DEFAULT_USER_AGENT) -> Optional[float]:
        """
        Returns the crawl-delay in seconds if specified in robots.txt.
        """
        domain = self.get_domain(url)
        if not domain:
            return None

        try:
            parser = await self.get_parser_for_domain(domain)
            delay = parser.crawl_delay(user_agent) or parser.crawl_delay("*")
            return float(delay) if delay is not None else None
        except Exception:
            return None
