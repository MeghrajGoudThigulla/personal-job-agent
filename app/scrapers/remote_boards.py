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

    async def scrape(self) -> List[Dict[str, Any]]:
        jobs = []
        async with httpx.AsyncClient(headers=self.DEFAULT_HEADERS, timeout=20.0, follow_redirects=True) as client:
            # 1. Jobicy
            try:
                jobicy_jobs = await self._scrape_jobicy(client)
                jobs.extend(jobicy_jobs)
            except Exception as e:
                logger.debug(f"Jobicy scrape error: {e}")

            # 2. RemoteOK
            try:
                remoteok_jobs = await self._scrape_remoteok(client)
                jobs.extend(remoteok_jobs)
            except Exception as e:
                logger.debug(f"RemoteOK scrape error: {e}")

            # 3. Remotive
            try:
                remotive_jobs = await self._scrape_remotive(client)
                jobs.extend(remotive_jobs)
            except Exception as e:
                logger.debug(f"Remotive scrape error: {e}")

            # 4. Arbeitnow
            try:
                arbeitnow_jobs = await self._scrape_arbeitnow(client)
                jobs.extend(arbeitnow_jobs)
            except Exception as e:
                logger.debug(f"Arbeitnow scrape error: {e}")

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
            results.append({
                "title": j.get("jobTitle", ""),
                "company": j.get("companyName", ""),
                "location": j.get("jobGeo", "Remote"),
                "remote_status": "Remote",
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
            results.append({
                "title": j.get("position", ""),
                "company": j.get("company", ""),
                "location": j.get("location", "Remote"),
                "remote_status": "Remote",
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
            results.append({
                "title": j.get("title", ""),
                "company": j.get("company_name", ""),
                "location": j.get("candidate_required_location", "Remote"),
                "remote_status": "Remote",
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
            results.append({
                "title": j.get("title", ""),
                "company": j.get("company_name", ""),
                "location": j.get("location", "Remote"),
                "remote_status": "Remote" if j.get("remote") else "Hybrid/Onsite",
                "url": j.get("url", ""),
                "source_platform": "Arbeitnow",
                "description": j.get("description", ""),
                "posted_date": j.get("created_at", "")
            })
        return results
