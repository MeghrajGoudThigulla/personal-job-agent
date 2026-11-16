"""
Analytics Funnel and Conversion Metrics API.
Provides high-level pipeline funnel tracking and source-by-source conversion statistics.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.models import JobPosting
from app.intelligence.skill_gap import SkillGapDetector

templates = Jinja2Templates(directory="app/templates")

router = APIRouter(tags=["Analytics"])



@router.get("/api/analytics/funnel")
async def get_analytics_funnel(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Returns application funnel metrics, stage conversion rates,
    and source-level performance.
    """
    # Funnel totals
    stmt_funnel = select(
        func.count(JobPosting.id).label("total_discovered"),
        func.sum(case((JobPosting.match_score >= 70.0, 1), else_=0)).label("total_qualified"),
        func.sum(case((JobPosting.status.in_(["reviewed", "applied", "interviewing", "offer", "rejected"]), 1), else_=0)).label("total_reviewed"),
        func.sum(case((JobPosting.applied_at.isnot(None) | JobPosting.status.in_(["applied", "interviewing", "offer", "rejected"]), 1), else_=0)).label("total_applied"),
        func.sum(case((JobPosting.interview_stage != "none", 1), (JobPosting.status.in_(["interviewing", "offer"]), 1), else_=0)).label("total_interviewing"),
        func.sum(case((JobPosting.status == "offer", 1), else_=0)).label("total_offers"),
        func.sum(case((JobPosting.status == "rejected", 1), else_=0)).label("total_rejected"),
    )
    res_funnel = await db.execute(stmt_funnel)
    row = res_funnel.first()

    total_discovered = int(row.total_discovered or 0)
    total_qualified = int(row.total_qualified or 0)
    total_reviewed = int(row.total_reviewed or 0)
    total_applied = int(row.total_applied or 0)
    total_interviewing = int(row.total_interviewing or 0)
    total_offers = int(row.total_offers or 0)
    total_rejected = int(row.total_rejected or 0)

    # Calculate conversion percentages
    match_rate = round((total_qualified / total_discovered * 100), 1) if total_discovered else 0.0
    apply_rate = round((total_applied / total_qualified * 100), 1) if total_qualified else 0.0
    interview_rate = round((total_interviewing / total_applied * 100), 1) if total_applied else 0.0
    offer_rate = round((total_offers / total_interviewing * 100), 1) if total_interviewing else 0.0

    # Source breakdown
    stmt_sources = (
        select(
            JobPosting.source_platform,
            func.count(JobPosting.id).label("total_jobs"),
            func.avg(JobPosting.match_score).label("avg_score"),
            func.sum(case((JobPosting.applied_at.isnot(None) | JobPosting.status.in_(["applied", "interviewing", "offer", "rejected"]), 1), else_=0)).label("applied_jobs"),
            func.sum(case((JobPosting.interview_stage != "none", 1), (JobPosting.status.in_(["interviewing", "offer"]), 1), else_=0)).label("interviews"),
            func.sum(case((JobPosting.status == "offer", 1), else_=0)).label("offers"),
        )
        .group_by(JobPosting.source_platform)
        .order_by(func.count(JobPosting.id).desc())
    )
    res_sources = await db.execute(stmt_sources)
    sources: List[Dict[str, Any]] = []
    for s in res_sources.all():
        sources.append({
            "source": s.source_platform or "Unknown",
            "total": int(s.total_jobs or 0),
            "avg_score": round(float(s.avg_score or 0.0), 1),
            "applied": int(s.applied_jobs or 0),
            "interviews": int(s.interviews or 0),
            "offers": int(s.offers or 0),
        })

    # Role Category breakdown
    stmt_categories = (
        select(
            JobPosting.role_category,
            func.count(JobPosting.id).label("total_jobs"),
            func.avg(JobPosting.match_score).label("avg_score"),
        )
        .group_by(JobPosting.role_category)
        .order_by(func.count(JobPosting.id).desc())
    )
    res_categories = await db.execute(stmt_categories)
    categories: List[Dict[str, Any]] = []
    for c in res_categories.all():
        categories.append({
            "category": c.role_category or "Uncategorized",
            "total": int(c.total_jobs or 0),
            "avg_score": round(float(c.avg_score or 0.0), 1),
        })

    return {
        "funnel": {
            "discovered": total_discovered,
            "qualified": total_qualified,
            "reviewed": total_reviewed,
            "applied": total_applied,
            "interviewing": total_interviewing,
            "offers": total_offers,
            "rejected": total_rejected,
        },
        "rates": {
            "match_rate": match_rate,
            "apply_rate": apply_rate,
            "interview_rate": interview_rate,
            "offer_rate": offer_rate,
        },
        "sources": sources,
        "categories": categories,
    }


@router.get("/api/analytics/skill-gaps")
async def get_market_skill_gaps(db: AsyncSession = Depends(get_db)) -> List[Dict[str, Any]]:
    """
    Returns market-wide missing skill frequencies and high-ROI upskilling recommendations.
    """
    stmt = select(JobPosting.match_reason).where(JobPosting.match_score >= 50.0)
    res = await db.execute(stmt)
    meta_list = []
    for (m_reason,) in res.all():
        if m_reason:
            try:
                data = json.loads(m_reason) if isinstance(m_reason, str) else m_reason
                meta_list.append(data)
            except Exception:
                pass

    detector = SkillGapDetector()
    return detector.aggregate_market_gaps(meta_list)


@router.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request, db: AsyncSession = Depends(get_db)):
    data = await get_analytics_funnel(db)
    market_gaps = await get_market_skill_gaps(db)
    return templates.TemplateResponse(
        request=request,
        name="analytics.html",
        context={
            "funnel": data["funnel"],
            "rates": data["rates"],
            "sources": data["sources"],
            "categories": data["categories"],
            "market_gaps": market_gaps,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        }
    )


