"""
Posting Liveness Checker.
Performs fast (<8s) deterministic HTTP checks against known ATS providers
(Lever, Ashby, Greenhouse, Workable, BambooHR, Paylocity, Workday) to verify
if a job posting is still live before wasting LLM tokens or alerting the user.
Inspired by AIHawk liveness architecture.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from urllib.parse import urlsplit
import httpx

logger = logging.getLogger(__name__)

OPEN = "open"
CLOSED = "closed"
UNCLEAR = "unclear"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
DEFAULT_TIMEOUT = 8.0
LOOKED_AT = 20000

GREENHOUSE_BOARDS = ("boards.greenhouse.io", "job-boards.greenhouse.io", "boards.eu.greenhouse.io")
WORKDAY_PATH = re.compile(r"^/(?:[a-z]{2}-[A-Z]{2}/)?([^/]+)/job/(.+)$")
WORKDAY_APPLY = re.compile(r"/(?:apply|applyManually)/?$")


def extract_title(html_text: str) -> str:
    """Extracts the <title> tag content from HTML."""
    match = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def workday_api_url(url: str) -> str:
    """Converts a Workday job posting URL into its CXS JSON endpoint."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if not host.endswith(".myworkdayjobs.com"):
        return ""
    clean_path = WORKDAY_APPLY.sub("", parts.path)
    match = WORKDAY_PATH.match(clean_path)
    if not match:
        return ""
    tenant = host.split(".")[0]
    site = match.group(1)
    job_path = match.group(2)
    return f"https://{host}/wday/cxs/{tenant}/{site}/job/{job_path}"


def bamboohr_api_url(url: str) -> str:
    """Returns BambooHR detail endpoint if the URL is a BambooHR careers link."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if not host.endswith(".bamboohr.com") or host == "www.bamboohr.com":
        return ""
    match = re.match(r"^/careers/(\d+)", parts.path)
    if not match:
        return ""
    return f"https://{host}/careers/{match.group(1)}/detail"


def greenhouse_api_url(url: str) -> str:
    """Converts Greenhouse job URL to public board API endpoint."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if host not in ("boards.greenhouse.io", "job-boards.greenhouse.io"):
        return ""
    match = re.match(r"^/([^/]+)/jobs/(\d+)", parts.path)
    if not match:
        return ""
    board = match.group(1)
    job_id = match.group(2)
    return f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"


def get_ats_provider(url: str) -> str | None:
    """Identifies the ATS provider from the URL hostname."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if "lever.co" in host:
        return "lever"
    if "ashbyhq.com" in host:
        return "ashby"
    if "greenhouse.io" in host:
        return "greenhouse"
    if "workable.com" in host:
        return "workable"
    if host.endswith(".bamboohr.com"):
        return "bamboohr"
    if "paylocity.com" in host:
        return "paylocity"
    if host.endswith(".myworkdayjobs.com"):
        return "workday"
    return None


def is_supported_ats(url: str) -> bool:
    """Returns True if the URL belongs to a supported ATS for liveness checking."""
    return get_ats_provider(url) is not None


def classify_response(provider: str, status: int, final_url: str, text: str = "") -> str:
    """
    Evaluates HTTP response to determine if the job is definitely closed, open, or unclear.
    """
    clean_url = final_url.split("#")[0]
    path = urlsplit(clean_url).path.rstrip("/")

    if provider == "lever":
        return CLOSED if status == 404 else OPEN if status == 200 else UNCLEAR

    if provider == "ashby":
        if status == 404:
            return CLOSED if extract_title(text) == "Jobs" else UNCLEAR
        return OPEN if status == 200 else UNCLEAR

    if provider == "greenhouse":
        if "error=true" in clean_url:
            return CLOSED
        if status == 200 and "page_title" not in text:
            return OPEN
        return UNCLEAR

    if provider == "greenhouse_api":
        return CLOSED if status == 404 else OPEN if status == 200 else UNCLEAR

    if provider == "workable":
        if urlsplit(clean_url).hostname == "apply.workable.com" and path == "/oops":
            return CLOSED
        return OPEN if status == 200 else UNCLEAR

    if provider == "bamboohr":
        if status == 404 or urlsplit(clean_url).hostname == "www.bamboohr.com" or path == "/careers":
            return CLOSED
        return OPEN if status == 200 and '"jobOpening"' in text else UNCLEAR

    if provider == "paylocity":
        if "/recruiting/jobs/jobnotfound" in clean_url.lower():
            return CLOSED
        return OPEN if status == 200 else UNCLEAR

    if provider == "workday":
        if status == 200 and "jobPostingInfo" in text:
            return OPEN
        if status == 403:
            try:
                data = json.loads(text)
                if isinstance(data, dict) and data.get("errorCode") == "S22":
                    return CLOSED
            except Exception:
                pass
        return UNCLEAR

    return UNCLEAR


async def check_liveness(url: str, client: httpx.AsyncClient | None = None) -> str:
    """
    Checks if a job posting URL is still active.
    Returns: 'open', 'closed', or 'unclear'.
    Never throws an exception; fails safe to 'unclear'.
    """
    provider = get_ats_provider(url)
    if not provider:
        return UNCLEAR

    target_url = url
    if provider == "workday":
        api = workday_api_url(url)
        if not api:
            return UNCLEAR
        target_url = api
    elif provider == "bamboohr":
        api = bamboohr_api_url(url)
        if not api:
            return UNCLEAR
        target_url = api

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.5",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        if client is not None:
            resp = await client.get(target_url, headers=headers, follow_redirects=True)
            verdict = classify_response(provider, resp.status_code, str(resp.url), resp.text[:LOOKED_AT])
            if provider == "greenhouse" and verdict == UNCLEAR:
                gh_api = greenhouse_api_url(url)
                if gh_api:
                    api_resp = await client.get(gh_api, headers=headers, follow_redirects=True)
                    verdict = classify_response("greenhouse_api", api_resp.status_code, str(api_resp.url), api_resp.text[:LOOKED_AT])
            return verdict

        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, follow_redirects=True, max_redirects=5) as own_client:
            resp = await own_client.get(target_url, headers=headers)
            verdict = classify_response(provider, resp.status_code, str(resp.url), resp.text[:LOOKED_AT])
            if provider == "greenhouse" and verdict == UNCLEAR:
                gh_api = greenhouse_api_url(url)
                if gh_api:
                    api_resp = await own_client.get(gh_api, headers=headers)
                    verdict = classify_response("greenhouse_api", api_resp.status_code, str(api_resp.url), api_resp.text[:LOOKED_AT])
            return verdict
    except Exception as e:
        logger.debug(f"Liveness check for {url} returned unclear due to: {e}")
        return UNCLEAR


async def posting_is_closed(url: str, client: httpx.AsyncClient | None = None) -> bool:
    """
    Returns True ONLY if the posting is unequivocally confirmed closed.
    Returns False if open, unclear, timed out, or unhandled ATS.
    """
    try:
        result = await asyncio.wait_for(check_liveness(url, client=client), timeout=DEFAULT_TIMEOUT)
        return result == CLOSED
    except Exception:
        return False
