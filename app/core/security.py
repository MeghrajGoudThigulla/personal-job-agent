from datetime import timedelta
import hmac
import logging
import secrets
from typing import Dict, List, Optional, Tuple
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.clock import utcnow
from app.core.models import LoginAttempt, SessionRecord

logger = logging.getLogger("personal_job_agent.security")

# In-memory failure timestamps per IP: {ip: [datetime, ...]}
_login_failures: Dict[str, List] = {}


def get_serializer() -> URLSafeTimedSerializer:
    secret = settings.SESSION_SECRET or "dev_default_session_secret_at_least_32_bytes_long_12345!"
    return URLSafeTimedSerializer(secret, salt="pja-session-auth")


def issue_session_cookie(sid: str) -> str:
    s = get_serializer()
    return s.dumps({"sid": sid, "iat": int(utcnow().timestamp())})


def verify_session_cookie(cookie_str: str) -> Optional[dict]:
    if not cookie_str:
        return None
    s = get_serializer()
    try:
        data = s.loads(cookie_str, max_age=7 * 86400)
        if isinstance(data, dict) and "sid" in data:
            return data
    except (BadSignature, SignatureExpired, Exception):
        return None
    return None


def constant_time_compare(val1: str, val2: str) -> bool:
    if not val1 or not val2:
        return False
    return hmac.compare_digest(val1.encode("utf-8"), val2.encode("utf-8"))


async def create_session(db: AsyncSession, client_ip: str = "") -> Tuple[SessionRecord, str]:
    sid = secrets.token_hex(32)
    csrf_token = secrets.token_hex(32)
    now = utcnow()
    expires_at = now + timedelta(days=7)

    record = SessionRecord(
        sid=sid,
        csrf_token=csrf_token,
        created_at=now,
        expires_at=expires_at,
        client_ip=client_ip[:50],
    )
    db.add(record)
    await db.commit()

    signed_cookie = issue_session_cookie(sid)
    return record, signed_cookie


async def get_valid_session(db: AsyncSession, sid: str) -> Optional[SessionRecord]:
    if not sid:
        return None
    stmt = select(SessionRecord).where(
        SessionRecord.sid == sid,
        SessionRecord.expires_at > utcnow()
    )
    res = await db.execute(stmt)
    return res.scalar_one_or_none()


async def invalidate_session(db: AsyncSession, sid: str) -> None:
    if not sid:
        return
    await db.execute(delete(SessionRecord).where(SessionRecord.sid == sid))
    await db.commit()


async def check_brute_force(db: AsyncSession, ip_address: str) -> Tuple[bool, int]:
    """
    Checks if client IP has exceeded 5 failed attempts in the last 15 minutes.
    Returns (is_blocked, retry_after_seconds).
    """
    now = utcnow()
    window_start = now - timedelta(minutes=15)

    # In-memory prune and count
    if ip_address in _login_failures:
        _login_failures[ip_address] = [t for t in _login_failures[ip_address] if t > window_start]
        mem_count = len(_login_failures[ip_address])
    else:
        mem_count = 0

    # DB count
    stmt = select(func.count(LoginAttempt.id)).where(
        LoginAttempt.ip_address == ip_address,
        LoginAttempt.success.is_(False),
        LoginAttempt.attempted_at >= window_start
    )
    db_count = (await db.execute(stmt)).scalar() or 0

    total_failures = max(mem_count, db_count)
    if total_failures >= 5:
        # Calculate retry after based on the earliest attempt in the window
        oldest = window_start
        if ip_address in _login_failures and _login_failures[ip_address]:
            oldest = min(_login_failures[ip_address])
        retry_after = max(1, 900 - int((now - oldest).total_seconds()))
        return True, retry_after

    return False, 0


async def record_login_attempt(db: AsyncSession, ip_address: str, success: bool) -> None:
    now = utcnow()
    if not success:
        if ip_address not in _login_failures:
            _login_failures[ip_address] = []
        _login_failures[ip_address].append(now)
    else:
        _login_failures.pop(ip_address, None)

    attempt = LoginAttempt(
        ip_address=ip_address[:50],
        attempted_at=now,
        success=success
    )
    db.add(attempt)
    await db.commit()

