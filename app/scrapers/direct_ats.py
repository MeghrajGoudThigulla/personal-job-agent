import asyncio
import logging
import json
import httpx
from typing import List, Dict, Any
from app.config import settings
from app.scrapers.base import BaseScraper

logger = logging.getLogger("personal_job_agent.scraper.ats")

class DirectATSScraper(BaseScraper):
    """
    Direct ATS Scraper querying public job board APIs for Greenhouse, Ashby, and Lever.
    Targets companies listed in Careers Pages Links.md and MPM JobHunt Cheat Sheet.
    """

    def __init__(self):
        super().__init__("DirectATSScraper")
        self.boards = self._load_boards()

    def _load_boards(self) -> Dict[str, List[str]]:
        if settings.COMPANY_TARGETS_JSON.exists():
            try:
                with open(settings.COMPANY_TARGETS_JSON, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("direct_ats_boards", {})
            except Exception:
                pass
        return {
            "ashby": ["linear", "posthog", "cal.com", "raycast", "supabase", "synthesia", "dust", "retool"],
            "greenhouse": ["anthropic", "openai", "stripe", "figma", "databricks", "snowflake", "vercel"],
            "lever": ["netlify", "palantir", "courier"]
        }

    async def _safe_fetch(self, coro, name: str) -> List[Dict[str, Any]]:
        try:
            return await asyncio.wait_for(coro, timeout=12.0)
        except Exception as e:
            logger.debug(f"ATS board {name} error/timeout: {e}")
            return []

    async def scrape(self) -> List[Dict[str, Any]]:
        jobs: List[Dict[str, Any]] = []
        limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
        async with httpx.AsyncClient(headers=self.DEFAULT_HEADERS, timeout=12.0, limits=limits, follow_redirects=True) as client:
            tasks = []
            for board in self.boards.get("ashby", []):
                tasks.append(self._safe_fetch(self._scrape_ashby(client, board), f"ashby:{board}"))
            for board in self.boards.get("greenhouse", []):
                tasks.append(self._safe_fetch(self._scrape_greenhouse(client, board), f"greenhouse:{board}"))
            for board in self.boards.get("lever", []):
                tasks.append(self._safe_fetch(self._scrape_lever(client, board), f"lever:{board}"))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, list):
                    jobs.extend(res)

        logger.info(f"DirectATSScraper discovered {len(jobs)} total postings across {len(tasks)} boards.")
        return jobs

    async def _scrape_ashby(self, client: httpx.AsyncClient, board: str) -> List[Dict[str, Any]]:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{board}"
        res = await client.get(url)
        if res.status_code != 200:
            return []
        data = res.json()
        results = []
        company_name = board.capitalize()
        for j in data.get("jobs", [])[:40]:
            title = j.get("title", "")
            location = j.get("location") or "Unknown"
            is_remote = j.get("isRemote", False)
            job_url = j.get("jobUrl", f"https://jobs.ashbyhq.com/{board}/{j.get('id')}")
            desc = j.get("descriptionHtml", "") or j.get("descriptionPlain", "")
            results.append({
                "title": title,
                "company": company_name,
                "location": location,
                "remote_status": "Remote" if is_remote or "remote" in location.lower() else ("Unknown" if location == "Unknown" else "Hybrid/Onsite"),
                "url": job_url,
                "source_platform": "Ashby",
                "description": desc,
                "posted_date": j.get("publishedAt", "")
            })
        return results

    async def _scrape_greenhouse(self, client: httpx.AsyncClient, board: str) -> List[Dict[str, Any]]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
        res = await client.get(url)
        if res.status_code != 200:
            return []
        data = res.json()
        results = []
        company_name = board.capitalize()
        for j in data.get("jobs", [])[:40]:
            title = j.get("title", "")
            loc = j.get("location", {}).get("name", "Unknown")
            job_url = j.get("absolute_url", "")
            desc = j.get("content", "")
            results.append({
                "title": title,
                "company": company_name,
                "location": loc,
                "remote_status": "Remote" if "remote" in loc.lower() else "Hybrid/Onsite",
                "url": job_url,
                "source_platform": "Greenhouse",
                "description": desc,
                "posted_date": j.get("updated_at", "")
            })
        return results

    async def _scrape_lever(self, client: httpx.AsyncClient, board: str) -> List[Dict[str, Any]]:
        url = f"https://api.lever.co/v0/postings/{board}?mode=json"
        res = await client.get(url)
        if res.status_code != 200:
            return []
        data = res.json()
        results = []
        company_name = board.capitalize()
        for j in data[:40]:
            title = j.get("text", "")
            cats = j.get("categories", {})
            loc = cats.get("location", "Unknown")
            job_url = j.get("hostedUrl", "")
            desc = j.get("descriptionPlain", "") or j.get("description", "")
            results.append({
                "title": title,
                "company": company_name,
                "location": loc,
                "remote_status": "Remote" if "remote" in loc.lower() else "Hybrid/Onsite",
                "url": job_url,
                "source_platform": "Lever",
                "description": desc,
                "posted_date": ""
            })
        return results
