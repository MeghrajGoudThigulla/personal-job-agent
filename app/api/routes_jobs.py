from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.core.database import get_db
from app.core.models import JobPosting, TailoredApplication

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])

@router.get("")
async def get_jobs(
    status: Optional[str] = None,
    min_score: Optional[float] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    query = select(JobPosting).order_by(desc(JobPosting.match_score), desc(JobPosting.discovered_at))

    if status and status != "all":
        query = query.where(JobPosting.status == status)
    if min_score is not None:
        query = query.where(JobPosting.match_score >= min_score)
    if source and source != "all":
        query = query.where(JobPosting.source_platform == source)
    if search:
        search_fmt = f"%{search}%"
        query = query.where(
            (JobPosting.title.ilike(search_fmt)) |
            (JobPosting.company.ilike(search_fmt)) |
            (JobPosting.role_category.ilike(search_fmt))
        )

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    jobs = result.scalars().all()

    return [j.to_dict() for j in jobs]

@router.get("/stats")
async def get_job_stats(db: AsyncSession = Depends(get_db)):
    total_jobs = await db.scalar(select(func.count(JobPosting.id)))
    high_match = await db.scalar(select(func.count(JobPosting.id)).where(JobPosting.match_score >= 70.0))
    tailored = await db.scalar(select(func.count(JobPosting.id)).where(JobPosting.status == "tailored"))
    applied = await db.scalar(select(func.count(JobPosting.id)).where(JobPosting.status == "applied"))
    notified = await db.scalar(select(func.count(JobPosting.id)).where(JobPosting.notified == True))

    return {
        "total_jobs": total_jobs or 0,
        "high_match": high_match or 0,
        "tailored": tailored or 0,
        "applied": applied or 0,
        "notified": notified or 0
    }

@router.get("/{job_id}")
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(JobPosting).where(JobPosting.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    data = job.to_dict()
    app_res = await db.execute(select(TailoredApplication).where(TailoredApplication.job_id == job_id))
    app_record = app_res.scalar_one_or_none()
    data["tailored_application"] = app_record.to_dict() if app_record else None
    return data

@router.patch("/{job_id}/status")
async def update_job_status(job_id: int, status: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(JobPosting).where(JobPosting.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.status = status
    await db.commit()
    return {"success": True, "job_id": job_id, "new_status": status}

@router.delete("/{job_id}")
async def delete_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(JobPosting).where(JobPosting.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    await db.delete(job)
    await db.commit()
    return {"success": True, "job_id": job_id}

@router.post("/cleanup")
async def trigger_manual_cleanup(days: Optional[int] = None, preserve_applied: bool = True):
    """
    Manually triggers data retention cleanup.
    Purges jobs older than `days` (defaults to DATA_RETENTION_DAYS, e.g. 60 days).
    """
    from app.core.cleanup import purge_old_records
    return await purge_old_records(retention_days=days, preserve_applied=preserve_applied)
