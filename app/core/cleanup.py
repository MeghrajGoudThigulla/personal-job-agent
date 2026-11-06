import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from sqlalchemy import select, delete
from app.config import settings
from app.core.database import async_session_factory
from app.core.models import JobPosting, TailoredApplication, AuditLog
from app.core.trace import log_audit_event

logger = logging.getLogger("personal_job_agent.cleanup")

async def purge_old_records(retention_days: Optional[int] = None, preserve_applied: bool = True) -> Dict[str, Any]:
    """
    Deletes job postings, tailored applications, and audit logs older than retention_days (default: 60 days).
    Example: With retention_days=60, in early January, all postings from November are automatically pruned.
    If preserve_applied is True, jobs marked as 'applied', 'interview', or 'offer' are kept.
    """
    days = retention_days if retention_days is not None else settings.DATA_RETENTION_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    logger.info(f"Starting data cleanup for records older than {days} days (cutoff: {cutoff.isoformat()})...")

    deleted_jobs = 0
    deleted_apps = 0
    deleted_logs = 0

    async with async_session_factory() as session:
        # Find jobs to purge
        stmt = select(JobPosting).where(JobPosting.discovered_at < cutoff)
        if preserve_applied:
            stmt = stmt.where(~JobPosting.status.in_(["applied", "interview", "offer"]))

        res = await session.execute(stmt)
        jobs_to_delete = res.scalars().all()

        for j in jobs_to_delete:
            # Check tailored application and remove disk files if any
            app_res = await session.execute(select(TailoredApplication).where(TailoredApplication.job_id == j.id))
            tailored_app = app_res.scalar_one_or_none()
            if tailored_app:
                if tailored_app.pdf_path and os.path.exists(tailored_app.pdf_path):
                    try:
                        os.remove(tailored_app.pdf_path)
                    except Exception:
                        pass
                await session.delete(tailored_app)
                deleted_apps += 1

            await session.delete(j)
            deleted_jobs += 1

        # Clean audit logs older than cutoff
        log_del = await session.execute(delete(AuditLog).where(AuditLog.timestamp < cutoff))
        deleted_logs = log_del.rowcount or 0

        await session.commit()

    summary = {
        "status": "success",
        "retention_days": days,
        "cutoff": cutoff.isoformat(),
        "deleted_jobs": deleted_jobs,
        "deleted_tailored_applications": deleted_apps,
        "deleted_audit_logs": deleted_logs
    }
    logger.info(f"Data cleanup completed: {summary}")
    try:
        await log_audit_event("data_cleanup", summary, "success")
    except Exception:
        pass
    return summary
