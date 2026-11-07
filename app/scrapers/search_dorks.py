import asyncio
import logging
import json
import urllib.parse
import re
from typing import List, Dict, Any, Tuple
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select

from app.config import settings
from app.scrapers.base import BaseScraper
from app.core.models import AppSetting

logger = logging.getLogger("personal_job_agent.scraper.dorks")

class SearchDorksScraper(BaseScraper):
    """
    Executes automated ATS Google/Search queries using a polite Round-Robin Batch Rotation.
    Rotates through all 121 personalized queries across all 11 roles and all 11 ATS platforms
    in sequential batches (default 8 queries per run) to prevent search engine rate limits or IP bans.
    """

    DEFAULT_BATCH_SIZE: int = 8
    _in_memory_cursor: int = 0

    def __init__(self):
        super().__init__("SearchDorksScraper")
        self.queries_data = self._load_queries()
        self.flat_queries = self._flatten_queries()

    def _load_queries(self) -> List[Dict[str, Any]]:
        if settings.PERSONALIZED_QUERIES_JSON.exists():
            try:
                with open(settings.PERSONALIZED_QUERIES_JSON, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("roles", [])
            except Exception as e:
                logger.error(f"Error loading personalized_queries.json: {e}")
        return []

    def _flatten_queries(self) -> List[Dict[str, Any]]:
        flat = []
        for r in self.queries_data:
            role_id = r.get("role_id")
            role_title = r.get("title", "")
            role_priority = r.get("priority", "P1")
            for p in r.get("platforms", []):
                flat.append({
                    "index": p.get("index", len(flat) + 1),
                    "role_id": role_id,
                    "role_title": role_title,
                    "priority": role_priority,
                    "platform": p.get("platform", "ATS"),
                    "site": p.get("site", ""),
                    "role_titles": p.get("role_titles", ""),
                    "tech_stack": p.get("tech_stack", ""),
                    "location": p.get("location", ""),
                    "seniority": p.get("seniority", ""),
                    "negatives": p.get("negatives", ""),
                    "full_query": p.get("full_query", "")
                })
        return flat

    async def get_cursor(self) -> int:
        """Retrieves persistent batch cursor from DB or falls back to in-memory."""
        try:
            from app.core.database import async_session_factory
            async with async_session_factory() as session:
                result = await session.execute(select(AppSetting).where(AppSetting.key == "dorks_batch_cursor"))
                setting = result.scalar_one_or_none()
                if setting and setting.value and setting.value.isdigit():
                    SearchDorksScraper._in_memory_cursor = int(setting.value)
                    return SearchDorksScraper._in_memory_cursor
        except Exception as e:
            logger.debug(f"Could not load dorks_batch_cursor from DB: {e}")
        return SearchDorksScraper._in_memory_cursor

    async def set_cursor(self, cursor: int):
        """Persists next batch cursor in DB."""
        SearchDorksScraper._in_memory_cursor = cursor
        try:
            from app.core.database import async_session_factory
            async with async_session_factory() as session:
                result = await session.execute(select(AppSetting).where(AppSetting.key == "dorks_batch_cursor"))
                setting = result.scalar_one_or_none()
                if setting:
                    setting.value = str(cursor)
                else:
                    session.add(AppSetting(key="dorks_batch_cursor", value=str(cursor)))
                await session.commit()
        except Exception as e:
            logger.debug(f"Could not persist dorks_batch_cursor to DB: {e}")

    def get_batch(self, cursor: int, batch_size: int = DEFAULT_BATCH_SIZE) -> Tuple[List[Dict[str, Any]], int]:
        """Returns the slice of queries for the given cursor, wrapping around cleanly."""
        total = len(self.flat_queries)
        if total == 0:
            return [], 0
        start = cursor % total
        batch = []
        for i in range(batch_size):
            batch.append(self.flat_queries[(start + i) % total])
        next_cursor = (start + batch_size) % total
        return batch, next_cursor

    async def get_status(self) -> Dict[str, Any]:
        """Returns diagnostic status of the round-robin query rotation."""
        cursor = await self.get_cursor()
        total = len(self.flat_queries)
        batch_size = self.DEFAULT_BATCH_SIZE
        current_batch = (cursor // batch_size) + 1 if batch_size else 1
        total_batches = (total + batch_size - 1) // batch_size if batch_size else 1
        batch, next_cursor = self.get_batch(cursor, batch_size)
        return {
            "total_queries": total,
            "batch_size": batch_size,
            "current_cursor": cursor,
            "next_cursor": next_cursor,
            "current_batch": current_batch,
            "total_batches": total_batches,
            "active_batch_queries": [
                {
                    "index": q["index"],
                    "role_title": q["role_title"],
                    "platform": q["platform"],
                    "priority": q["priority"]
                }
                for q in batch
            ]
        }

    async def scrape(self, batch_size: int = DEFAULT_BATCH_SIZE) -> List[Dict[str, Any]]:
        """
        Executes the current round-robin batch of ATS search queries.
        Advances the persistent cursor after execution.
        """
        total = len(self.flat_queries)
        if total == 0:
            logger.warning("No personalized queries found to execute.")
            return []

        cursor = await self.get_cursor()
        batch, next_cursor = self.get_batch(cursor, batch_size)
        current_batch_num = (cursor // batch_size) + 1
        total_batches = (total + batch_size - 1) // batch_size

        logger.info(
            f"SearchDorksScraper: Executing Batch {current_batch_num}/{total_batches} "
            f"(Queries #{batch[0]['index']}..#{batch[-1]['index']} of {total})..."
        )

        jobs = []
        async with httpx.AsyncClient(headers=self.DEFAULT_HEADERS, timeout=20.0, follow_redirects=True) as client:
            for i, q in enumerate(batch):
                clean_query = q.get("full_query") or f"{q.get('site')} {q.get('role_titles')} {q.get('tech_stack')} {q.get('location')}"
                logger.info(f"Query [{i+1}/{len(batch)}] #{q['index']}: {q['role_title']} on {q['platform']}")
                try:
                    results = await self._search_ddg(client, clean_query, q.get("role_title"))
                    jobs.extend(results)
                except Exception as e:
                    logger.debug(f"Search dork error for query #{q['index']}: {e}")

                # Polite pause between queries to avoid search engine rate limits
                if i < len(batch) - 1:
                    await asyncio.sleep(1.5)

        # Advance and persist cursor for next cycle
        await self.set_cursor(next_cursor)
        logger.info(
            f"SearchDorksScraper: Batch {current_batch_num} complete. Found {len(jobs)} postings. "
            f"Next batch begins at query #{next_cursor + 1}."
        )
        return jobs

    async def _search_ddg(self, client: httpx.AsyncClient, query: str, role_category: str) -> List[Dict[str, Any]]:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        res = await client.get(url)
        if res.status_code != 200:
            return []

        soup = BeautifulSoup(res.text, "html.parser")
        results = []

        for a in soup.find_all("div", class_="result__body")[:10]:
            title_tag = a.find("a", class_="result__a")
            snippet_tag = a.find("a", class_="result__snippet")
            if not title_tag:
                continue

            raw_url = title_tag.get("href", "")
            if "uddg=" in raw_url:
                match = re.search(r"uddg=([^&]+)", raw_url)
                if match:
                    raw_url = urllib.parse.unquote(match.group(1))

            title_text = title_tag.get_text(strip=True)
            snippet_text = snippet_tag.get_text(strip=True) if snippet_tag else ""

            # Verify URL belongs to an ATS platform
            ats_domains = [
                "ashbyhq.com", "greenhouse.io", "lever.co", "myworkdayjobs.com",
                "smartrecruiters.com", "icims.com", "bamboohr.com", "jobvite.com",
                "jazz.co", "workable.com"
            ]
            if any(ats in raw_url.lower() for ats in ats_domains):
                company_guess = "ATS Company"
                if "ashbyhq.com/" in raw_url:
                    parts = raw_url.split("ashbyhq.com/")[1].split("/")
                    if parts:
                        company_guess = parts[0].replace("-", " ").title()
                elif "greenhouse.io/" in raw_url:
                    parts = raw_url.split("greenhouse.io/")[1].split("/")
                    if parts:
                        company_guess = parts[0].replace("-", " ").title()
                elif "lever.co/" in raw_url:
                    parts = raw_url.split("lever.co/")[1].split("/")
                    if parts:
                        company_guess = parts[0].replace("-", " ").title()
                elif "myworkdayjobs.com/" in raw_url:
                    match_wd = re.search(r"https?://([^.]+)\.", raw_url)
                    if match_wd:
                        company_guess = match_wd.group(1).replace("-", " ").title()
                elif "smartrecruiters.com/" in raw_url:
                    parts = raw_url.split("smartrecruiters.com/")[1].split("/")
                    if parts:
                        company_guess = parts[0].replace("-", " ").title()
                elif "workable.com/" in raw_url:
                    parts = raw_url.split("workable.com/")[1].split("/")
                    if parts:
                        company_guess = parts[0].replace("-", " ").title()

                # Extract location from snippet or title
                detected_location = "India / Remote"
                snippet_lower = f"{title_text} {snippet_text}".lower()
                for ind in ["bengaluru", "bangalore", "hyderabad", "pune", "mumbai", "gurgaon", "gurugram", "noida", "chennai", "delhi", "coimbatore"]:
                    if ind in snippet_lower:
                        detected_location = f"{ind.title()}, India"
                        break
                if "remote" in snippet_lower and ("india" in snippet_lower or "apac" in snippet_lower):
                    detected_location = "Remote - India"

                results.append({
                    "title": title_text,
                    "company": company_guess,
                    "location": detected_location,
                    "remote_status": "Remote" if "remote" in snippet_text.lower() or "remote" in title_text.lower() else "Hybrid/Onsite",
                    "url": raw_url,
                    "source_platform": "SearchDork",
                    "description": snippet_text,
                    "posted_date": ""
                })

        return results
