import asyncio
import logging
from typing import List, Dict, Any
from app.scrapers.base import BaseScraper

logger = logging.getLogger("personal_job_agent.scraper.jobspy")

class JobSpyScraper(BaseScraper):
    """
    Scrapes LinkedIn, Indeed, and Glassdoor using python-jobspy.
    Targeted for Software Engineer, AI Engineer, and Backend roles in India / Remote.
    """

    def __init__(self):
        super().__init__("JobSpyScraper")

    async def scrape(self) -> List[Dict[str, Any]]:
        jobs = []
        try:
            from jobspy import scrape_jobs

            search_terms = [
                "Python Backend Developer",
                "FastAPI Developer",
                "Python Developer 1-2 years",
                "Full Stack Python React",
                ".NET Developer 1-2 years",
                "Flutter Developer",
                "Junior Software Engineer Python"
            ]
            for term in search_terms:
                try:
                    df = await asyncio.to_thread(
                        scrape_jobs,
                        site_name=["indeed"], # Indeed works cleanly from datacenter IPs without proxy
                        search_term=term,
                        location="India",
                        results_wanted=15,
                        hours_old=72,
                        country_indeed="india"
                    )
                    if df is not None and not df.empty:
                        for _, row in df.iterrows():
                            jobs.append({
                                "title": str(row.get("title", "")),
                                "company": str(row.get("company", "")),
                                "location": str(row.get("location", "India")),
                                "remote_status": "Remote" if row.get("is_remote") else "Hybrid/Onsite",
                                "url": str(row.get("job_url", "")),
                                "source_platform": str(row.get("site", "JobSpy")),
                                "description": str(row.get("description", ""))[:3000],
                                "posted_date": str(row.get("date_posted", ""))
                            })
                except Exception as inner_e:
                    logger.debug(f"JobSpy scrape search error for {term}: {inner_e}")
        except ImportError:
            logger.warning("python-jobspy not available. Skipping multi-board scrape.")
        except Exception as e:
            logger.error(f"JobSpy scraper error: {e}")

        logger.info(f"JobSpyScraper extracted {len(jobs)} jobs.")
        return jobs
