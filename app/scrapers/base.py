import abc
import logging
from typing import List, Dict, Any
import httpx

logger = logging.getLogger("personal_job_agent.scraper.base")

class BaseScraper(abc.ABC):
    """Abstract base class for all job scrapers."""

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/html, */*",
        "Accept-Language": "en-US,en;q=0.9"
    }

    def __init__(self, name: str):
        self.name = name

    @abc.abstractmethod
    async def scrape(self) -> List[Dict[str, Any]]:
        """
        Executes scraper and returns list of standardized job dictionaries:
        {
            "title": str,
            "company": str,
            "location": str,
            "remote_status": str,
            "url": str,
            "source_platform": str,
            "description": str,
            "posted_date": str
        }
        """
        pass
