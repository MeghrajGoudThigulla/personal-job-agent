#!/usr/bin/env python3
"""
Short-lived subprocess runner for python-jobspy.
Runs multi-board job scrapes across Indeed, LinkedIn, Naukri, Glassdoor, Google Jobs,
and ZipRecruiter, and prints JSON output to stdout.
Running in a subprocess ensures all memory consumed by pandas, numpy, and curl_cffi
is immediately reclaimed by the OS upon process exit.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
logger = logging.getLogger("run_jobspy")

SUPPORTED_SITES = {
    "indeed", "linkedin", "naukri", "glassdoor", "google",
    "zip_recruiter", "bayt", "bdjobs", "hellowork"
}

SITE_NAMES_MAP = {
    "indeed": "Indeed",
    "linkedin": "LinkedIn",
    "naukri": "Naukri",
    "glassdoor": "Glassdoor",
    "google": "Google Jobs",
    "zip_recruiter": "ZipRecruiter",
    "bayt": "Bayt",
    "bdjobs": "BDJobs",
    "hellowork": "HelloWork",
}

DEFAULT_SEARCH_TERMS = [
    "Python Developer",
    "FastAPI Developer",
    "Full Stack Python React",
    "Flutter Developer",
]


def normalize_site_name(site: str) -> str:
    clean = site.strip().lower()
    if clean in ("ziprecruiter", "zip-recruiter"):
        return "zip_recruiter"
    if clean in ("googlejobs", "google-jobs"):
        return "google"
    return clean


def run_jobspy(
    search_terms: List[str],
    sites: Optional[List[str]] = None,
    location: str = "India",
    country: str = "india",
    results_wanted: int = 5,
    hours_old: int = 72,
    proxies: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    try:
        from jobspy import scrape_jobs
    except ImportError as e:
        logger.warning(f"python-jobspy or dependencies not installed: {e}")
        return []

    raw_sites = sites or ["indeed", "linkedin", "naukri", "glassdoor"]
    normalized_sites = [
        normalize_site_name(s)
        for s in raw_sites
        if normalize_site_name(s) in SUPPORTED_SITES
    ]
    target_sites = normalized_sites or ["indeed"]

    jobs = []
    seen_urls = set()

    for term in search_terms:
        try:
            kwargs: Dict[str, Any] = {
                "site_name": target_sites,
                "search_term": term,
                "location": location,
                "results_wanted": results_wanted,
                "hours_old": hours_old,
                "country_indeed": country,
                "description_format": "markdown",
            }
            if proxies:
                kwargs["proxies"] = proxies

            df = scrape_jobs(**kwargs)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    url = str(row.get("job_url", "")).strip()
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    raw_site = str(row.get("site", "jobspy")).lower()
                    platform_name = SITE_NAMES_MAP.get(raw_site, raw_site.capitalize())

                    jobs.append({
                        "title": str(row.get("title", "")).strip(),
                        "company": str(row.get("company", "")).strip(),
                        "location": str(row.get("location", location)).strip(),
                        "remote_status": "Remote" if row.get("is_remote") else "Hybrid/Onsite",
                        "url": url,
                        "source_platform": platform_name,
                        "description": str(row.get("description", ""))[:4000],
                        "posted_date": str(row.get("date_posted", "")),
                    })
        except Exception as e:
            logger.warning(f"JobSpy scrape error for term '{term}' on sites {target_sites}: {e}")

    return jobs


def main():
    parser = argparse.ArgumentParser(description="Run python-jobspy in a short-lived subprocess.")
    parser.add_argument("--terms", nargs="*", default=DEFAULT_SEARCH_TERMS, help="Search terms")
    parser.add_argument("--sites", nargs="*", default=["indeed", "linkedin", "naukri", "glassdoor"], help="Sites to scrape")
    parser.add_argument("--location", default="India", help="Search location")
    parser.add_argument("--country", default="india", help="Country for Indeed")
    parser.add_argument("--results-wanted", type=int, default=5, help="Results wanted per term (default 5)")
    parser.add_argument("--hours-old", type=int, default=72, help="Max hours old")
    parser.add_argument("--proxies", nargs="*", default=None, help="Proxy URLs for rotation")
    args = parser.parse_args()

    results = run_jobspy(
        search_terms=args.terms,
        sites=args.sites,
        location=args.location,
        country=args.country,
        results_wanted=args.results_wanted,
        hours_old=args.hours_old,
        proxies=args.proxies,
    )
    print(json.dumps(results))


if __name__ == "__main__":
    main()
