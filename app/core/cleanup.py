from datetime import timedelta
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from sqlalchemy import delete, select
from app.config import settings
from app.core.clock import utcnow
from app.core.database import async_session_factory
from app.core.models import AuditLog, JobPosting, SeenJob, TailoredApplication
from app.core.trace import log_audit_event

logger = logging.getLogger("personal_job_agent.cleanup")
CHUNK_SIZE = 500


def is_safe_resume_path(file_path: Optional[str]) -> bool:
    """Verifies that the target path resolves strictly inside data/tailored_resumes."""
    if not file_path:
        return False
    try:
        resumes_dir = Path("data/tailored_resumes").resolve()
        target = Path(file_path).resolve()
        return target.is_file() and resumes_dir in target.parents
    except (ValueError, OSError):
        return False


async def purge_old_records(retention_days: Optional[int] = None, preserve_applied: bool = True) -> Dict[str, Any]:
    """
    Deletes job postings, tailored applications, and audit logs older than DATA_RETENTION_DAYS (default: 60 days).
    Keeps seen_jobs records for SEEN_RETENTION_DAYS (default: 365 days) to prevent re-opening duplicates.
    Runs chunked bulk deletes in batches of 500 to prevent unbounded memory usage and DB lock contention.
    Safely deletes PDF files ensuring they resolve strictly inside data/tailored_resumes.
    """
    days = retention_days if retention_days is not None else settings.DATA_RETENTION_DAYS
    seen_days = settings.SEEN_RETENTION_DAYS
    now = utcnow()
    cutoff = now - timedelta(days=days)
    seen_cutoff = now - timedelta(days=seen_days)

    logger.info(
        f"Starting data cleanup (jobs cutoff: {cutoff.isoformat()}, seen_jobs cutoff: {seen_cutoff.isoformat()})..."
    )

    deleted_jobs = 0
    deleted_apps = 0
    deleted_logs = 0
    deleted_seen = 0

    async with async_session_factory() as session:
        # 1. Chunked deletion of jobs and associated tailored applications
        while True:
            subq = select(JobPosting.id).where(JobPosting.discovered_at < cutoff)
            if preserve_applied:
                subq = subq.where(~JobPosting.status.in_(["applied", "interview", "offer"]))
            subq = subq.limit(CHUNK_SIZE)

            job_ids = (await session.execute(subq)).scalars().all()
            if not job_ids:
                break

            # Find and clean tailored applications & disk files
            app_stmt = select(TailoredApplication.id, TailoredApplication.pdf_path).where(
                TailoredApplication.job_id.in_(job_ids)
            )
            app_rows = (await session.execute(app_stmt)).all()
            for app_row in app_rows:
                if is_safe_resume_path(app_row.pdf_path):
                    try:
                        Path(app_row.pdf_path).resolve().unlink(missing_ok=True)
                    except Exception as unlink_err:
                        logger.warning(f"Failed to remove resume PDF {app_row.pdf_path}: {unlink_err}")

            if app_rows:
                app_ids = [r.id for r in app_rows]
                del_app_res = await session.execute(
                    delete(TailoredApplication).where(TailoredApplication.id.in_(app_ids))
                )
                deleted_apps += (del_app_res.rowcount or len(app_ids))

            # Delete jobs batch
            del_jobs_res = await session.execute(
                delete(JobPosting).where(JobPosting.id.in_(job_ids))
            )
            deleted_jobs += (del_jobs_res.rowcount or len(job_ids))
            await session.commit()

        # 2. Chunked deletion of audit logs older than cutoff
        while True:
            log_subq = select(AuditLog.id).where(AuditLog.timestamp < cutoff).limit(CHUNK_SIZE)
            log_ids = (await session.execute(log_subq)).scalars().all()
            if not log_ids:
                break

            del_log_res = await session.execute(delete(AuditLog).where(AuditLog.id.in_(log_ids)))
            deleted_logs += (del_log_res.rowcount or len(log_ids))
            await session.commit()

        # 3. Chunked deletion of seen_jobs older than SEEN_RETENTION_DAYS
        while True:
            seen_subq = select(SeenJob.url_hash).where(SeenJob.last_seen_at < seen_cutoff).limit(CHUNK_SIZE)
            seen_hashes = (await session.execute(seen_subq)).scalars().all()
            if not seen_hashes:
                break

            del_seen_res = await session.execute(delete(SeenJob).where(SeenJob.url_hash.in_(seen_hashes)))
            deleted_seen += (del_seen_res.rowcount or len(seen_hashes))
            await session.commit()

    summary = {
        "status": "success",
        "retention_days": days,
        "seen_retention_days": seen_days,
        "cutoff": cutoff.isoformat(),
        "seen_cutoff": seen_cutoff.isoformat(),
        "deleted_jobs": deleted_jobs,
        "deleted_tailored_applications": deleted_apps,
        "deleted_audit_logs": deleted_logs,
        "deleted_seen_jobs": deleted_seen,
    }
    logger.info(f"Data cleanup completed: {summary}")
    try:
        await log_audit_event("data_cleanup", summary, "success")
    except Exception:
        pass
    return summary
