import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from app.core.database import async_session_factory
from app.core.models import AuditLog

logger = logging.getLogger("personal_job_agent.trace")

async def log_audit_event(action: str, details: Any, status: str = "success") -> None:
    """
    Logs an audit event in compliance with the AI Collaboration Field Guide.
    Ensures every AI action, scraper run, and notification has a verifiable trace.
    Includes lock retry resilience for SQLite concurrency.
    """
    try:
        details_str = json.dumps(details) if not isinstance(details, str) else details
        for attempt in range(3):
            try:
                async with async_session_factory() as session:
                    audit = AuditLog(
                        timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
                        action=action,
                        details=details_str,
                        status=status
                    )
                    session.add(audit)
                    await session.commit()
                break
            except Exception as lock_err:
                if "locked" in str(lock_err).lower() and attempt < 2:
                    await asyncio.sleep(0.2 * (attempt + 1))
                    continue
                raise lock_err
    except Exception as e:
        logger.error(f"Failed to record audit log: {e}")
