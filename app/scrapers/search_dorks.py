import logging
import json
import urllib.parse
import re
from typing import List, Dict, Any
import httpx
from bs4 import BeautifulSoup
from app.config import settings
from app.scrapers.base import BaseScraper

logger = logging.getLogger("personal_job_agent.scraper.dorks")

class SearchDorksScraper(BaseScraper):
    """
    Executes automated Google/ATS search queries from My Personalized Job Queries.md
    using DuckDuckGo search endpoint to discover fresh job listings across all 11 ATS platforms.
    """

    def __init__(self):
        super().__init__("SearchDorksScraper")
        self.queries_data = self._load_queries()

    def _load_queries(self) -> List[Dict[str, Any]]:
        if settings.PERSONALIZED_QUERIES_JSON.exists():
            try:
                with open(settings.PERSONALIZED_QUERIES_JSON, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("roles", [])
            except Exception:
                pass
        return []

    async def scrape(self, max_roles: int = 4) -> List[Dict[str, Any]]:
        """Scrapes newly indexed ATS links for the priority roles."""
        jobs = []
        # Target high priority roles (P1)
        target_roles = [r for r in self.queries_data if r.get("priority") == "P1"][:max_roles]

        async with httpx.AsyncClient(headers=self.DEFAULT_HEADERS, timeout=20.0, follow_redirects=True) as client:
            for role in target_roles:
                platforms = role.get("platforms", [])
                # Query top ATS platforms (Ashby, Greenhouse, Lever, Workday)
                for p in platforms[:3]:
                    site = p.get("site", "")
                    clean_query = f"{site} {p.get('role_titles', '')} {p.get('tech_stack', '')} {p.get('location', '')}".strip()
                    try:
                        results = await self._search_ddg(client, clean_query, role.get("title"))
                        jobs.extend(results)
                    except Exception as e:
                        logger.debug(f"Search dork error for query '{clean_query[:40]}': {e}")

        logger.info(f"SearchDorksScraper discovered {len(jobs)} postings via ATS dorks.")
        return jobs

    async def _search_ddg(self, client: httpx.AsyncClient, query: str, role_category: str) -> List[Dict[str, Any]]:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        res = await client.get(url)
        if res.status_code != 200:
            return []

        soup = BeautifulSoup(res.text, "html.parser")
        results = []
        links = soup.find_all("a", class_="result__url")
        titles = soup.find_all("a", class_="result__snippet")

        for a in soup.find_all("div", class_="result__body")[:10]:
            title_tag = a.find("a", class_="result__a")
            snippet_tag = a.find("a", class_="result__snippet")
            if not title_tag:
                continue

            raw_url = title_tag.get("href", "")
            # Duckduckgo redirect link unpacking
            if "uddg=" in raw_url:
                match = re.search(r"uddg=([^&]+)", raw_url)
                if match:
                    raw_url = urllib.parse.unquote(match.group(1))

            title_text = title_tag.get_text(strip=True)
            snippet_text = snippet_tag.get_text(strip=True) if snippet_tag else ""

            # Check if url belongs to an ATS platform
            if any(ats in raw_url for ats in ["ashbyhq.com", "greenhouse.io", "lever.co", "myworkdayjobs.com", "smartrecruiters.com"]):
                # Extract company guess from url or title
                company_guess = "ATS Company"
                if "ashbyhq.com/" in raw_url:
                    parts = raw_url.split("ashbyhq.com/")[1].split("/")
                    if parts: company_guess = parts[0].replace("-", " ").title()
                elif "greenhouse.io/" in raw_url:
                    parts = raw_url.split("greenhouse.io/")[1].split("/")
                    if parts: company_guess = parts[0].replace("-", " ").title()
                elif "lever.co/" in raw_url:
                    parts = raw_url.split("lever.co/")[1].split("/")
                    if parts: company_guess = parts[0].replace("-", " ").title()

                # Extract location from snippet or title; never fabricate India
                detected_location = "Unknown"
                snippet_lower = f"{title_text} {snippet_text}".lower()
                for ind in ["bengaluru", "bangalore", "hyderabad", "pune", "mumbai", "gurgaon", "gurugram", "noida", "chennai", "delhi", "india"]:
                    if ind in snippet_lower:
                        detected_location = f"{ind.title()}, India" if ind != "india" else "India"
                        break
                if "remote" in snippet_lower and "india" in snippet_lower:
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
