import logging
import json
from typing import List, Dict, Any
import httpx
from bs4 import BeautifulSoup
from app.config import settings
from app.scrapers.base import BaseScraper

logger = logging.getLogger("personal_job_agent.scraper.company")

class CompanyCareerScraper(BaseScraper):
    """
    Scrapes company careers pages listed in Careers Pages Links.md.
    """

    def __init__(self):
        super().__init__("CompanyCareerScraper")
        self.target_links = self._load_target_links()

    def _load_target_links(self) -> List[str]:
        if settings.COMPANY_TARGETS_JSON.exists():
            try:
                with open(settings.COMPANY_TARGETS_JSON, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for cat in data.get("categories", []):
                        if "BIG TECH" in cat.get("category", "") or "REMOTE" in cat.get("category", ""):
                            return cat.get("links", [])[:10]
            except Exception:
                pass
        return []

    async def scrape(self) -> List[Dict[str, Any]]:
        jobs = []
        async with httpx.AsyncClient(headers=self.DEFAULT_HEADERS, timeout=15.0, follow_redirects=True) as client:
            for link in self.target_links[:5]:
                try:
                    res = await client.get(link)
                    if res.status_code == 200:
                        soup = BeautifulSoup(res.text, "html.parser")
                        # Basic title check
                        page_title = soup.title.string if soup.title else link
                        jobs.append({
                            "title": "Software Engineering Opportunities",
                            "company": page_title.split("-")[0].split("|")[0].strip(),
                            "location": "Remote / Hybrid",
                            "remote_status": "Remote",
                            "url": link,
                            "source_platform": "CompanyCareer",
                            "description": f"Careers portal check: {page_title}",
                            "posted_date": ""
                        })
                except Exception as e:
                    logger.debug(f"Company career error for {link}: {e}")

        return jobs
