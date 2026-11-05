import os
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from app.config import settings
from app.core.database import init_db, get_db
from app.core.models import JobPosting, TailoredApplication, AuditLog, AppSetting
from app.core.scheduler import start_scheduler, stop_scheduler
from app.api.routes_jobs import router as jobs_router
from app.api.routes_tailor import router as tailor_router
from app.api.routes_scraper import router as scraper_router
from app.api.routes_settings import router as settings_router
from app.api.routes_trace import router as trace_router

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database & Load Saved Settings
    await init_db()
    
    # Load persisted settings overrides from SQLite
    try:
        from app.core.database import async_session_factory
        async with async_session_factory() as session:
            result = await session.execute(select(AppSetting))
            overrides = result.scalars().all()
            for rec in overrides:
                if hasattr(settings, rec.key):
                    val = rec.value
                    if rec.key in ("PORT", "MIN_MATCH_SCORE_NOTIFY", "SCRAPE_INTERVAL_MINUTES", "SMTP_PORT"):
                        val = int(val)
                    elif rec.key in ("SCHEDULER_ENABLED", "AUTO_TAILOR_HIGH_MATCH", "EMAIL_NOTIFY_ENABLED"):
                        val = val.lower() in ("true", "1")
                    setattr(settings, rec.key, val)
    except Exception as e:
        pass

    # Start Background Job Scheduler
    start_scheduler()
    
    yield
    
    # Shutdown
    stop_scheduler()

app = FastAPI(
    title=settings.APP_NAME,
    description="Automated Job Discovery, STAIR Match Scoring, and Anti-Slop Resume Tailoring Agent for Meghraj Goud Thigulla",
    version="1.0.0",
    lifespan=lifespan
)

# Include API Routers
app.include_router(jobs_router)
app.include_router(tailor_router)
app.include_router(scraper_router)
app.include_router(settings_router)
app.include_router(trace_router)

# Mount static files if present
static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# -------------------------------------------------------------
# Web UI Routes
# -------------------------------------------------------------

@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def dashboard_view(
    request: Request,
    status: Optional[str] = None,
    min_score: Optional[float] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    # Query stats
    total_jobs = await db.scalar(select(func.count(JobPosting.id))) or 0
    high_match = await db.scalar(select(func.count(JobPosting.id)).where(JobPosting.match_score >= 70.0)) or 0
    tailored = await db.scalar(select(func.count(JobPosting.id)).where(JobPosting.status == "tailored")) or 0
    applied = await db.scalar(select(func.count(JobPosting.id)).where(JobPosting.status == "applied")) or 0

    stats = {
        "total_jobs": total_jobs,
        "high_match": high_match,
        "tailored": tailored,
        "applied": applied
    }

    # Query jobs
    query = select(JobPosting).order_by(desc(JobPosting.match_score), desc(JobPosting.discovered_at))
    if status and status != "all":
        query = query.where(JobPosting.status == status)
    if min_score is not None and min_score > 0:
        query = query.where(JobPosting.match_score >= min_score)
    if source and source != "all":
        query = query.where(JobPosting.source_platform == source)
    if search:
        s_fmt = f"%{search}%"
        query = query.where(
            (JobPosting.title.ilike(s_fmt)) |
            (JobPosting.company.ilike(s_fmt)) |
            (JobPosting.role_category.ilike(s_fmt))
        )

    query = query.limit(100)
    res = await db.execute(query)
    jobs = res.scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "stats": stats,
            "jobs": [j.to_dict() for j in jobs]
        }
    )

@app.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail_view(request: Request, job_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(JobPosting).where(JobPosting.id == job_id))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job_dict = job.to_dict()
    
    # Parse STAIR match metadata
    match_meta = {}
    try:
        match_meta = json.loads(job.match_reason) if job.match_reason else {}
    except Exception:
        pass

    # Load tailored application if exists
    app_res = await db.execute(select(TailoredApplication).where(TailoredApplication.job_id == job_id))
    app_record = app_res.scalar_one_or_none()
    
    linkedin_messages = {}
    if app_record and app_record.linkedin_4mm:
        try:
            linkedin_messages = json.loads(app_record.linkedin_4mm)
        except Exception:
            pass

    job_dict["application"] = app_record.to_dict() if app_record else None

    return templates.TemplateResponse(
        request=request,
        name="job_detail.html",
        context={
            "job": job_dict,
            "match_meta": match_meta,
            "linkedin_messages": linkedin_messages
        }
    )

@app.get("/settings", response_class=HTMLResponse)
async def settings_view(request: Request):
    def mask(val: str) -> str:
        if not val or len(val) < 8:
            return "" if not val else "********"
        return f"{val[:4]}...{val[-4:]}"

    current_settings = {
        "groq_api_key_masked": mask(settings.GROQ_API_KEY),
        "nvidia_nim_api_key_masked": mask(settings.NVIDIA_NIM_API_KEY),
        "telegram_bot_token_masked": mask(settings.TELEGRAM_BOT_TOKEN),
        "telegram_chat_id_masked": mask(settings.TELEGRAM_CHAT_ID),
        "discord_webhook_url_masked": mask(settings.DISCORD_WEBHOOK_URL)
    }

    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={
            "settings": settings,
            "current_settings": current_settings
        }
    )

@app.get("/trace", response_class=HTMLResponse)
async def trace_view(request: Request, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(AuditLog).order_by(desc(AuditLog.timestamp)).limit(50))
    logs = res.scalars().all()
    return templates.TemplateResponse(
        request=request,
        name="audit_logs.html",
        context={
            "logs": [l.to_dict() for l in logs]
        }
    )

@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    """Health check endpoint for Render deployment."""
    return {
        "status": "healthy",
        "service": "personal-job-agent",
        "env": settings.ENV,
        "scheduler_running": start_scheduler is not None
    }
