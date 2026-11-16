"""
Application Kanban Tracker & Interview Rounds API.
Allows tracking job postings from Discovery through Application, Interviews,
and Final Outcomes. Inspired by JobSync Kanban architecture.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.database import get_db
from app.core.models import JobPosting, InterviewRound

router = APIRouter(prefix="/api/tracker", tags=["Application Tracker"])


class UpdateJobStatusPayload(BaseModel):
    job_id: int
    status: str  # new, reviewed, tailored, applied, interviewing, offer, rejected, archived, withdrawn
    interview_stage: Optional[str] = None  # none, screening, technical, system_design, final, hr
    notes: Optional[str] = None
    rejection_reason: Optional[str] = None


class CreateInterviewRoundPayload(BaseModel):
    job_id: int
    round_number: int = 1
    round_type: str = "technical"  # screening, technical, system_design, final, hr
    interviewer_name: Optional[str] = ""
    outcome: Optional[str] = "pending"  # pending, passed, failed
    notes: Optional[str] = ""


@router.get("/kanban")
async def get_kanban_board(db: AsyncSession = Depends(get_db)) -> Dict[str, List[Dict[str, Any]]]:
    """
    Returns jobs partitioned by Kanban stage:
    discovered -> applied -> interviewing -> offer -> rejected
    """
    stmt = select(JobPosting).order_by(desc(JobPosting.match_score), desc(JobPosting.discovered_at))
    result = await db.execute(stmt)
    jobs = result.scalars().all()

    board: Dict[str, List[Dict[str, Any]]] = {
        "discovered": [],
        "applied": [],
        "interviewing": [],
        "offer": [],
        "rejected": [],
    }

    for job in jobs:
        st = (job.status or "new").lower()
        job_data = job.to_dict(include_description=False)

        if st in ("applied",):
            board["applied"].append(job_data)
        elif st in ("interviewing",):
            board["interviewing"].append(job_data)
        elif st in ("offer",):
            board["offer"].append(job_data)
        elif st in ("rejected", "archived", "withdrawn"):
            board["rejected"].append(job_data)
        else:
            board["discovered"].append(job_data)

    return board


@router.post("/status")
async def update_job_status(payload: UpdateJobStatusPayload, db: AsyncSession = Depends(get_db)):
    """Updates a job's application tracking status, interview stage, or notes."""
    job = await db.get(JobPosting, payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found")

    old_status = job.status
    job.status = payload.status

    if payload.status == "applied" and not job.applied_at:
        job.applied_at = utcnow()

    if payload.interview_stage is not None:
        job.interview_stage = payload.interview_stage
    elif payload.status == "interviewing" and (not job.interview_stage or job.interview_stage == "none"):
        job.interview_stage = "screening"

    if payload.notes is not None:
        job.notes = payload.notes

    if payload.rejection_reason is not None:
        job.rejection_reason = payload.rejection_reason

    await db.commit()
    await db.refresh(job)

    return {
        "status": "success",
        "job_id": job.id,
        "old_status": old_status,
        "new_status": job.status,
        "interview_stage": job.interview_stage,
        "applied_at": job.applied_at.isoformat() if job.applied_at else None,
    }


@router.post("/interview")
async def add_interview_round(payload: CreateInterviewRoundPayload, db: AsyncSession = Depends(get_db)):
    """Logs an interview round for an active job application."""
    job = await db.get(JobPosting, payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found")

    # If job wasn't marked as interviewing, automatically update status
    if job.status not in ("interviewing", "offer"):
        job.status = "interviewing"
        job.interview_stage = payload.round_type

    round_record = InterviewRound(
        job_id=payload.job_id,
        round_number=payload.round_number,
        round_type=payload.round_type,
        interviewer_name=payload.interviewer_name or "",
        outcome=payload.outcome or "pending",
        notes=payload.notes or "",
    )
    db.add(round_record)
    await db.commit()
    await db.refresh(round_record)

    return {
        "status": "success",
        "interview_round": round_record.to_dict(),
    }


@router.delete("/interview/{round_id}")
async def delete_interview_round(round_id: int, db: AsyncSession = Depends(get_db)):
    """Deletes an interview round record."""
    record = await db.get(InterviewRound, round_id)
    if not record:
        raise HTTPException(status_code=404, detail="Interview round not found")

    await db.delete(record)
    await db.commit()
    return {"status": "success", "deleted_round_id": round_id}


@router.get("/stats")
async def get_tracker_stats(db: AsyncSession = Depends(get_db)):
    """Computes high-level application funnel and conversion statistics."""
    stmt = select(JobPosting)
    result = await db.execute(stmt)
    all_jobs = result.scalars().all()

    total_discovered = len(all_jobs)
    total_applied = sum(1 for j in all_jobs if j.status in ("applied", "interviewing", "offer", "rejected") or j.applied_at)
    total_interviewing = sum(1 for j in all_jobs if j.status == "interviewing")
    total_offers = sum(1 for j in all_jobs if j.status == "offer")
    total_rejected = sum(1 for j in all_jobs if j.status == "rejected")

    interview_rate = round((total_interviewing + total_offers) / max(1, total_applied) * 100, 1)

    return {
        "total_discovered": total_discovered,
        "total_applied": total_applied,
        "total_interviewing": total_interviewing,
        "total_offers": total_offers,
        "total_rejected": total_rejected,
        "interview_conversion_rate_pct": interview_rate,
    }
