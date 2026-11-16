import asyncio
import json
import logging
import sys
from typing import Any, Dict, List
from app.config import settings
from app.scrapers.base import BaseScraper

logger = logging.getLogger("personal_job_agent.scraper.jobspy")

class JobSpyScraper(BaseScraper):
    """
    Scrapes Indeed using python-jobspy inside a short-lived subprocess.
    Ensures pandas, numpy, and curl_cffi memory is immediately reclaimed by the OS.
    """

    def __init__(self):
        super().__init__("JobSpyScraper")

    async def scrape(self) -> List[Dict[str, Any]]:
        if not settings.JOBSPY_ENABLED:
            logger.info("JobSpy scraping is disabled via JOBSPY_ENABLED=false. Skipping.")
            return []

        script_path = settings.BASE_DIR / "scripts" / "run_jobspy.py"
        if not script_path.exists():
            logger.warning(f"JobSpy runner script not found at {script_path}. Skipping.")
            return []

        sites = [s.strip() for s in settings.JOBSPY_SITES.split(",") if s.strip()] or ["indeed"]
        cmd = [
            sys.executable,
            str(script_path),
            "--results-wanted", str(settings.JOBSPY_RESULTS_WANTED),
            "--location", "India",
            "--country", "india",
            "--sites", *sites,
        ]

        if settings.JOBSPY_PROXIES:
            proxies = [p.strip() for p in settings.JOBSPY_PROXIES.split(",") if p.strip()]
            if proxies:
                cmd.extend(["--proxies", *proxies])

        logger.info(f"Executing JobSpy scraper for sites {sites} in a short-lived subprocess...")
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120.0)

            if proc.returncode != 0:
                err_msg = stderr.decode("utf-8", errors="replace").strip()
                logger.warning(f"JobSpy subprocess exited with code {proc.returncode}: {err_msg[:300]}")
                return []

            output_str = stdout.decode("utf-8", errors="replace").strip()
            if not output_str:
                return []

            jobs = json.loads(output_str)
            logger.info(f"JobSpyScraper extracted {len(jobs)} jobs via isolated subprocess.")
            return jobs
        except asyncio.TimeoutError:
            logger.warning("JobSpy subprocess timed out after 120s; terminating process.")
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
            return []
        except Exception as e:
            logger.error(f"Failed to execute JobSpy subprocess: {e}")
            return []
