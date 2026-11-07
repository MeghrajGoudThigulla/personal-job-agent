import abc
from datetime import datetime, timedelta, timezone
import logging
import re
from typing import Any, Dict, List, Optional
from dateutil import parser as date_parser

from app.core.clock import utcnow

logger = logging.getLogger("personal_job_agent.scraper.base")


def parse_posted_date(raw: Any) -> Optional[datetime]:
    """
    Parses a variety of date formats into an aware UTC datetime:
    - None / empty string -> None
    - datetime objects -> aware UTC datetime
    - Numeric epoch timestamps (seconds or milliseconds)
    - ISO 8601 strings (e.g. '2026-11-05T12:00:00Z', '2026-11-05')
    - Relative time strings (e.g. '3 days ago', '12 hours ago', 'yesterday', 'just posted', 'today')
    """
    if raw is None:
        return None

    now = utcnow()

    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)

    # If numeric (int or float)
    if isinstance(raw, (int, float)):
        try:
            val = float(raw)
            if val > 1e11:  # Milliseconds
                return datetime.fromtimestamp(val / 1000.0, tz=timezone.utc)
            return datetime.fromtimestamp(val, tz=timezone.utc)
        except Exception:
            return None

    if not isinstance(raw, str):
        raw = str(raw)

    s = raw.strip()
    if not s:
        return None

    # Numeric string (e.g. "1730985600" or "1730985600000")
    if s.isdigit():
        try:
            val = float(s)
            if val > 1e11:
                return datetime.fromtimestamp(val / 1000.0, tz=timezone.utc)
            return datetime.fromtimestamp(val, tz=timezone.utc)
        except Exception:
            pass

    s_lower = s.lower()

    # Relative time strings
    if s_lower in ("just posted", "just now", "today", "moments ago", "few seconds ago"):
        return now

    if s_lower == "yesterday":
        return now - timedelta(days=1)

    m_hour = re.search(r"(\d+)\s*(?:hours?|hrs?|h)\s*ago", s_lower)
    if m_hour:
        return now - timedelta(hours=int(m_hour.group(1)))

    m_min = re.search(r"(\d+)\s*(?:minutes?|mins?|m)\s*ago", s_lower)
    if m_min:
        return now - timedelta(minutes=int(m_min.group(1)))

    m_day = re.search(r"(\d+)\s*(?:days?|d)\s*ago", s_lower)
    if m_day:
        return now - timedelta(days=int(m_day.group(1)))

    m_week = re.search(r"(\d+)\s*(?:weeks?|wks?|w)\s*ago", s_lower)
    if m_week:
        return now - timedelta(weeks=int(m_week.group(1)))

    m_month = re.search(r"(\d+)\s*(?:months?|mo)\s*ago", s_lower)
    if m_month:
        return now - timedelta(days=int(m_month.group(1)) * 30)

    # Standard ISO and text parsing with dateutil
    try:
        dt = date_parser.parse(s)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    return None


class BaseScraper(abc.ABC):
    """Abstract base class for all job scrapers."""

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/html, */*",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self, name: str):
        self.name = name

    @abc.abstractmethod
    async def scrape(self) -> List[Dict[str, Any]]:
        """
        Executes scraper and returns list of standardized job dictionaries:
        {
            "title": str,
            "company": str,
            "location": str,
            "remote_status": str,
            "url": str,
            "source_platform": str,
            "description": str,
            "posted_date": str
        }
        """
        pass
