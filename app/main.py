import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func, select
from sqlalchemy.orm import defer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes_jobs import router as jobs_router
from app.api.routes_scraper import router as scraper_router
from app.api.routes_settings import router as settings_router
from app.api.routes_tailor import router as tailor_router
from app.api.routes_trace import router as trace_router
from app.config import settings
from app.core.clock import format_ist, to_ist, utcnow
from app.core.database import async_session_factory, get_db, init_db
from app.core.models import AppSetting, AuditLog, JobPosting, TailoredApplication
from app.core.scheduler import get_scheduler_status, start_scheduler, stop_scheduler
from app.core.system import get_process_memory_mb
from app.core.security import (
    check_brute_force,
    constant_time_compare,
    create_session,
    invalidate_session,
    record_login_attempt,
    verify_session_cookie,
)

logger = logging.getLogger("personal_job_agent.main")

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

templates.env.filters["to_ist"] = to_ist
templates.env.filters["format_ist"] = format_ist

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
    except Exception:
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

PUBLIC_PATHS = {"/health", "/health/live", "/health/ready", "/login"}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if path in PUBLIC_PATHS or path.startswith("/static/"):
        return await call_next(request)

    # 1. Bearer Token or X-API-Key Authentication (CSRF exempt)
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.split(" ", 1)[1].strip() if auth_header.startswith("Bearer ") else ""
    api_key = request.headers.get("X-API-Key", "")

    if (token and constant_time_compare(token, settings.APP_PASSWORD)) or (
        api_key and constant_time_compare(api_key, settings.APP_PASSWORD)
    ):
        request.state.auth_type = "api"
        return await call_next(request)

    # 2. Signed Session Cookie Authentication
    session_cookie = request.cookies.get(settings.ADMIN_SESSION_COOKIE, "")
    if session_cookie:
        cookie_data = verify_session_cookie(session_cookie)
        if cookie_data and "sid" in cookie_data:
            from app.core.security import get_valid_session

            async with async_session_factory() as db:
                session_rec = await get_valid_session(db, cookie_data["sid"])
                if session_rec:
                    request.state.auth_type = "cookie"
                    request.state.session = session_rec
                    request.state.csrf_token = session_rec.csrf_token

                    # CSRF Verification for Cookie-authenticated mutating requests (logout is exempt)
                    if request.method not in ("GET", "HEAD", "OPTIONS") and path != "/logout":
                        csrf_header = request.headers.get("X-CSRF-Token", "")
                        if not csrf_header or not constant_time_compare(csrf_header, session_rec.csrf_token):
                            return JSONResponse(
                                status_code=403,
                                content={"detail": "CSRF token missing or invalid"},
                            )

                    return await call_next(request)

    if path.startswith("/api/"):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized: Valid authentication required"})

    return RedirectResponse(url="/login", status_code=303)


# -------------------------------------------------------------
# Web UI Routes
# -------------------------------------------------------------


def _render_login_html(error: str = "") -> str:
    err_html = f'<p class="text-xs text-rose-400 font-semibold text-center">{error}</p>' if error else ""
    return f"""<!DOCTYPE html>
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
        {err_html}
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
</html>"""


@app.get("/login", response_class=HTMLResponse)
async def login_view(request: Request):
    session_cookie = request.cookies.get(settings.ADMIN_SESSION_COOKIE, "")
    if session_cookie:
        cookie_data = verify_session_cookie(session_cookie)
        if cookie_data and "sid" in cookie_data:
            from app.core.security import get_valid_session

            async with async_session_factory() as db:
                if await get_valid_session(db, cookie_data["sid"]):
                    return RedirectResponse(url="/", status_code=303)

    return HTMLResponse(_render_login_html())


@app.post("/login")
async def login_submit(request: Request):
    forwarded = request.headers.get("x-forwarded-for")
    client_ip = (
        forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "127.0.0.1")
    )

    async with async_session_factory() as db:
        is_blocked, retry_after = await check_brute_force(db, client_ip)
        if is_blocked:
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content={"detail": "Too many failed login attempts. Try again later."},
            )

        password = ""
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                body = await request.json()
                password = body.get("password", "")
            except Exception:
                pass
        else:
            form = await request.form()
            password = form.get("password", "")

        if constant_time_compare(password, settings.APP_PASSWORD):
            await record_login_attempt(db, client_ip, success=True)
            _, signed_cookie = await create_session(db, client_ip)

            secure_flag = settings.ENV != "development"
            resp = (
                RedirectResponse(url="/", status_code=303)
                if "application/json" not in content_type
                else JSONResponse({"status": "ok"})
            )
            resp.set_cookie(
                key=settings.ADMIN_SESSION_COOKIE,
                value=signed_cookie,
                httponly=True,
                secure=secure_flag,
                samesite="strict",
                path="/",
                max_age=7 * 86400,
            )
            return resp

        # On failure: constant 300 ms delay, record failure, log only IP and timestamp
        await asyncio.sleep(0.3)
        await record_login_attempt(db, client_ip, success=False)
        logger.warning(f"Failed login attempt from IP {client_ip} at {utcnow().isoformat()}")

        if "application/json" in content_type:
            return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})
        return HTMLResponse(_render_login_html(error="Invalid credentials"), status_code=401)


@app.api_route("/logout", methods=["GET", "POST"])
async def logout(request: Request):
    session_cookie = request.cookies.get(settings.ADMIN_SESSION_COOKIE, "")
    if session_cookie:
        cookie_data = verify_session_cookie(session_cookie)
        if cookie_data and "sid" in cookie_data:
            async with async_session_factory() as db:
                await invalidate_session(db, cookie_data["sid"])

    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(settings.ADMIN_SESSION_COOKIE, path="/")
    return resp
    return resp

@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def dashboard_view(
    request: Request,
    status: Optional[str] = None,
    min_score: Optional[float] = None,
    tier: Optional[str] = None,
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

    # Query jobs (defer description to reduce memory overhead on list view)
    query = (
        select(JobPosting)
        .options(defer(JobPosting.description))
        .order_by(desc(JobPosting.match_score), desc(JobPosting.discovered_at))
    )
    if status and status != "all":
        query = query.where(JobPosting.status == status)
    if tier and tier != "all":
        if tier == "unverified":
            query = query.where(JobPosting.match_tier == "Excluded (Location Unverified)")
        else:
            query = query.where(JobPosting.match_tier == tier)
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
            "jobs": [j.to_dict(include_description=False) for j in jobs],
            "csrf_token": getattr(request.state, "csrf_token", ""),
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
            "linkedin_messages": linkedin_messages,
            "csrf_token": getattr(request.state, "csrf_token", ""),
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
            "current_settings": current_settings,
            "csrf_token": getattr(request.state, "csrf_token", ""),
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
            "logs": [log.to_dict() for log in logs],
            "csrf_token": getattr(request.state, "csrf_token", ""),
        }
    )

@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    """Public health check endpoint returning minimal status."""
    return {"status": "ok"}

@app.api_route("/health/live", methods=["GET", "HEAD"])
async def health_live():
    """Liveness probe returning minimal status."""
    return {"status": "ok"}

@app.api_route("/health/ready", methods=["GET", "HEAD"])
async def health_ready():
    """Readiness probe checking database connectivity."""
    try:
        from app.core.database import async_session_factory
        from sqlalchemy import text
        from fastapi.responses import JSONResponse
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"status": "error", "detail": "Database unavailable"})

@app.get("/api/health/detailed")
async def health_detailed(request: Request):
    """Authenticated endpoint returning detailed scheduler and system status."""
    sched_info = get_scheduler_status()
    return {
        "status": "ok",
        "service": "personal-job-agent",
        "env": settings.ENV,
        "scheduler_running": sched_info["running"],
        "scrape_interval_minutes": sched_info["interval_minutes"],
        "next_scrape_at": sched_info["next_scrape_at"],
        "next_cleanup_at": sched_info.get("next_cleanup_at"),
        "retention_days": sched_info.get("retention_days"),
        "memory_rss_mb": get_process_memory_mb(),
    }
