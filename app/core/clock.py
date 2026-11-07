from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo
from sqlalchemy import DateTime, TypeDecorator

IST = ZoneInfo("Asia/Kolkata")
UTC = timezone.utc


def utcnow() -> datetime:
    """Returns a timezone-aware UTC datetime."""
    return datetime.now(UTC)


def to_ist(dt: Optional[datetime]) -> Optional[datetime]:
    """Converts a datetime (assumed UTC if naive) to Asia/Kolkata timezone."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(IST)


def format_ist(dt: Optional[datetime], fmt: str = "%Y-%m-%d %H:%M:%S IST") -> str:
    """Formats a datetime in Asia/Kolkata timezone."""
    ist_dt = to_ist(dt)
    if ist_dt is None:
        return ""
    return ist_dt.strftime(fmt)


class UTCDateTime(TypeDecorator):
    """
    SQLAlchemy TypeDecorator that guarantees timezone-aware UTC datetimes
    across SQLite and PostgreSQL backends.
    """
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if not isinstance(value, datetime):
                raise TypeError(f"Expected datetime.datetime, got {type(value)}")
            if value.tzinfo is None:
                value = value.replace(tzinfo=UTC)
            else:
                value = value.astimezone(UTC)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                value = value.replace(tzinfo=UTC)
            else:
                value = value.astimezone(UTC)
        return value
