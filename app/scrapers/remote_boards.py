import asyncio
import logging
import httpx
from typing import List, Dict, Any
from app.scrapers.base import BaseScraper

logger = logging.getLogger("personal_job_agent.scraper.remote")

class RemoteBoardsScraper(BaseScraper):
    """
    Scrapes established remote job board JSON feeds:
    - Jobicy
    - RemoteOK
    - Remotive
    - Arbeitnow
    """

    def __init__(self):
        super().__init__("RemoteBoardsScraper")

    async def _safe_fetch(self, coro, name: str) -> List[Dict[str, Any]]:
        try:
            return await asyncio.wait_for(coro, timeout=10.0)
        except Exception as e:
            logger.debug(f"Remote board {name} error/timeout: {e}")
            return []

    async def scrape(self) -> List[Dict[str, Any]]:
        jobs: List[Dict[str, Any]] = []
        limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
        async with httpx.AsyncClient(headers=self.DEFAULT_HEADERS, timeout=10.0, limits=limits, follow_redirects=True) as client:
            tasks = [
                self._safe_fetch(self._scrape_jobicy(client), "Jobicy"),
                self._safe_fetch(self._scrape_remoteok(client), "RemoteOK"),
                self._safe_fetch(self._scrape_remotive(client), "Remotive"),
                self._safe_fetch(self._scrape_arbeitnow(client), "Arbeitnow"),
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, list):
                    jobs.extend(res)

        logger.info(f"RemoteBoardsScraper discovered {len(jobs)} postings.")
        return jobs

    async def _scrape_jobicy(self, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
        url = "https://jobicy.com/api/v2/remote-jobs?count=50"
        res = await client.get(url)
        if res.status_code != 200:
            return []
        data = res.json()
        results = []
        for j in data.get("jobs", []):
            loc = j.get("jobGeo") or "Unknown"
            results.append({
                "title": j.get("jobTitle", ""),
                "company": j.get("companyName", ""),
                "location": loc,
                "remote_status": "Remote" if "remote" in loc.lower() else ("Unknown" if loc == "Unknown" else "Hybrid/Onsite"),
                "url": j.get("url", ""),
                "source_platform": "Jobicy",
                "description": j.get("jobDescription", ""),
                "posted_date": j.get("pubDate", "")
            })
        return results

    async def _scrape_remoteok(self, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
        url = "https://remoteok.com/api"
        res = await client.get(url)
        if res.status_code != 200:
            return []
        data = res.json()
        results = []
        # RemoteOK first element is legal notice
        items = data[1:] if isinstance(data, list) and len(data) > 1 else []
        for j in items[:50]:
            if not isinstance(j, dict):
                continue
            loc = j.get("location") or "Unknown"
            results.append({
                "title": j.get("position", ""),
                "company": j.get("company", ""),
                "location": loc,
                "remote_status": "Remote" if "remote" in loc.lower() else ("Unknown" if loc == "Unknown" else "Hybrid/Onsite"),
                "url": j.get("url", f"https://remoteok.com/l/{j.get('id')}"),
                "source_platform": "RemoteOK",
                "description": j.get("description", ""),
                "posted_date": j.get("date", "")
            })
        return results

    async def _scrape_remotive(self, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
        url = "https://remotive.com/api/remote-jobs?category=software-dev&limit=50"
        res = await client.get(url)
        if res.status_code != 200:
            return []
        data = res.json()
        results = []
        for j in data.get("jobs", []):
            loc = j.get("candidate_required_location") or "Unknown"
            results.append({
                "title": j.get("title", ""),
                "company": j.get("company_name", ""),
                "location": loc,
                "remote_status": "Remote" if "remote" in loc.lower() else ("Unknown" if loc == "Unknown" else "Hybrid/Onsite"),
                "url": j.get("url", ""),
                "source_platform": "Remotive",
                "description": j.get("description", ""),
                "posted_date": j.get("publication_date", "")
            })
        return results

    async def _scrape_arbeitnow(self, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
        url = "https://arbeitnow.com/api/job-board-api"
        res = await client.get(url)
        if res.status_code != 200:
            return []
        data = res.json()
        results = []
        for j in data.get("data", []):
            loc = j.get("location") or "Unknown"
            results.append({
                "title": j.get("title", ""),
                "company": j.get("company_name", ""),
                "location": loc,
                "remote_status": "Remote" if j.get("remote") or "remote" in loc.lower() else ("Unknown" if loc == "Unknown" else "Hybrid/Onsite"),
                "url": j.get("url", ""),
                "source_platform": "Arbeitnow",
                "description": j.get("description", ""),
                "posted_date": j.get("created_at", "")
            })
        return results
