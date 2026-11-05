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
    """
    try:
        details_str = json.dumps(details) if not isinstance(details, str) else details
        async with async_session_factory() as session:
            audit = AuditLog(
                timestamp=datetime.now(timezone.utc),
                action=action,
                details=details_str,
                status=status
            )
            session.add(audit)
            await session.commit()
    except Exception as e:
        logger.error(f"Failed to record audit log: {e}")
