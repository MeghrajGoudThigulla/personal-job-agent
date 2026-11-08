#!/usr/bin/env python3
"""
Short-lived subprocess runner for python-jobspy.
Runs Indeed/multi-board job scrapes and prints JSON output to stdout.
Running in a subprocess ensures all memory consumed by pandas, numpy, and curl_cffi
is immediately reclaimed by the OS upon process exit.
"""

import argparse
import json
import logging
import sys
from typing import Any, Dict, List

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
logger = logging.getLogger("run_jobspy")

DEFAULT_SEARCH_TERMS = [
    "Python Developer",
    "FastAPI Developer",
    "Full Stack Python React",
    "Flutter Developer"
]

def run_jobspy(
    search_terms: List[str],
    location: str = "India",
    results_wanted: int = 5,
    hours_old: int = 72,
) -> List[Dict[str, Any]]:
    try:
        from jobspy import scrape_jobs
    except ImportError as e:
        logger.warning(f"python-jobspy or dependencies not installed: {e}")
        return []

    jobs = []
    seen_urls = set()

    for term in search_terms:
        try:
            df = scrape_jobs(
                site_name=["indeed"],
                search_term=term,
                location=location,
                results_wanted=results_wanted,
                hours_old=hours_old,
                country_indeed="india",
            )
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    url = str(row.get("job_url", "")).strip()
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    jobs.append({
                        "title": str(row.get("title", "")).strip(),
                        "company": str(row.get("company", "")).strip(),
                        "location": str(row.get("location", location)).strip(),
                        "remote_status": "Remote" if row.get("is_remote") else "Hybrid/Onsite",
                        "url": url,
                        "source_platform": str(row.get("site", "JobSpy")),
                        "description": str(row.get("description", ""))[:3000],
                        "posted_date": str(row.get("date_posted", "")),
                    })
        except Exception as e:
            logger.warning(f"JobSpy scrape error for '{term}': {e}")

    return jobs

def main():
    parser = argparse.ArgumentParser(description="Run python-jobspy in a short-lived subprocess.")
    parser.add_argument("--terms", nargs="*", default=DEFAULT_SEARCH_TERMS, help="Search terms")
    parser.add_argument("--location", default="India", help="Search location")
    parser.add_argument("--results-wanted", type=int, default=5, help="Results wanted per term (default 5)")
    parser.add_argument("--hours-old", type=int, default=72, help="Max hours old")
    args = parser.parse_args()

    results = run_jobspy(
        search_terms=args.terms,
        location=args.location,
        results_wanted=args.results_wanted,
        hours_old=args.hours_old,
    )
    print(json.dumps(results))

if __name__ == "__main__":
    main()
