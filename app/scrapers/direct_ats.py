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

    async def scrape(self) -> List[Dict[str, Any]]:
        jobs = []
        async with httpx.AsyncClient(headers=self.DEFAULT_HEADERS, timeout=20.0, follow_redirects=True) as client:
            # 1. Ashby Boards
            for board in self.boards.get("ashby", []):
                try:
                    ashby_jobs = await self._scrape_ashby(client, board)
                    jobs.extend(ashby_jobs)
                except Exception as e:
                    logger.debug(f"Ashby board {board} error: {e}")

            # 2. Greenhouse Boards
            for board in self.boards.get("greenhouse", []):
                try:
                    gh_jobs = await self._scrape_greenhouse(client, board)
                    jobs.extend(gh_jobs)
                except Exception as e:
                    logger.debug(f"Greenhouse board {board} error: {e}")

            # 3. Lever Boards
            for board in self.boards.get("lever", []):
                try:
                    lever_jobs = await self._scrape_lever(client, board)
                    jobs.extend(lever_jobs)
                except Exception as e:
                    logger.debug(f"Lever board {board} error: {e}")

        logger.info(f"DirectATSScraper discovered {len(jobs)} total postings.")
        return jobs

    async def _scrape_ashby(self, client: httpx.AsyncClient, board: str) -> List[Dict[str, Any]]:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{board}"
        res = await client.get(url)
        if res.status_code != 200:
            return []
        data = res.json()
        results = []
        company_name = board.capitalize()
        for j in data.get("jobs", []):
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
        for j in data.get("jobs", []):
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
        for j in data:
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
