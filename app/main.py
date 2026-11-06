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
from app.core.scheduler import start_scheduler, stop_scheduler, get_scheduler_status
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
# Security & Single-User Authentication Middleware
# -------------------------------------------------------------

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if settings.APP_PASSWORD:
        path = request.url.path
        # Public endpoints that never require auth
        if path == "/health" or path == "/login" or path.startswith("/static"):
            return await call_next(request)

        # Check Authorization header, X-API-Key, or secure Session Cookie
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.split(" ", 1)[1].strip() if auth_header.startswith("Bearer ") else ""
        api_key = request.headers.get("X-API-Key", "")
        session_cookie = request.cookies.get(settings.ADMIN_SESSION_COOKIE, "")

        if token == settings.APP_PASSWORD or api_key == settings.APP_PASSWORD or session_cookie == settings.APP_PASSWORD:
            return await call_next(request)

        if path.startswith("/api/"):
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=401, content={"detail": "Unauthorized: Valid APP_PASSWORD required"})
        
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login", status_code=303)

    return await call_next(request)

# -------------------------------------------------------------
# Web UI Routes
# -------------------------------------------------------------

@app.get("/login", response_class=HTMLResponse)
async def login_view(request: Request):
    return HTMLResponse("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login · Project Veronica</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
</head>
<body class="bg-gray-900 text-gray-100 flex items-center justify-center min-h-screen p-4">
    <div class="bg-gray-800 border border-gray-700 p-8 rounded-xl shadow-2xl max-w-sm w-full space-y-5">
        <div class="text-center">
            <h1 class="text-2xl font-black text-indigo-400">PROJECT VERONICA</h1>
            <p class="text-xs text-gray-400 mt-1">Meghraj's Autonomous Job Search Agent</p>
        </div>
        <form method="POST" action="/login" class="space-y-4">
            <div>
                <label class="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-2">Access Password</label>
                <input type="password" name="password" placeholder="Enter APP_PASSWORD" required
                       class="w-full px-4 py-2.5 bg-gray-900 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition">
            </div>
            <button type="submit" class="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-lg shadow-lg hover:shadow-indigo-500/30 transition">
                Authenticate
            </button>
        </form>
    </div>
</body>
</html>""")

@app.post("/login")
async def login_submit(request: Request):
    from fastapi.responses import RedirectResponse
    form = await request.form()
    password = form.get("password", "")
    if password == settings.APP_PASSWORD:
        resp = RedirectResponse(url="/", status_code=303)
        resp.set_cookie(key=settings.ADMIN_SESSION_COOKIE, value=password, httponly=True, max_age=86400 * 30, samesite="lax")
        return resp
    raise HTTPException(status_code=401, detail="Invalid password")

@app.get("/logout")
async def logout_view():
    from fastapi.responses import RedirectResponse
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(settings.ADMIN_SESSION_COOKIE)
    return resp

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
    """Health check endpoint for Render deployment and monitoring."""
    sched_info = get_scheduler_status()
    return {
        "status": "healthy",
        "service": "personal-job-agent",
        "env": settings.ENV,
        "scheduler_running": sched_info["running"],
        "scrape_interval_minutes": sched_info["interval_minutes"],
        "next_scrape_at": sched_info["next_scrape_at"]
    }
