# Personal Job Agent (Project Veronica) - System Overview & Architecture

## 📋 Executive Summary
**Project Veronica** is an automated, AI-augmented job discovery, matching, and application preparation engine. Operating in tandem with the **JARVIS** Telegram bot, it scrapes target ATS platforms (Greenhouse, Lever, Ashby, Workable, SmartRecruiters), evaluates postings using a calibrated multi-factor STAIR matching matrix against candidate credentials, and drafts strictly tailored, anti-slop LaTeX and Markdown resumes with automatic multi-channel notifications and cold outreach drafts.

---

## 🏛️ System Architecture

```
                          ┌───────────────────────────┐
                          │   cron-job.org / Monitor  │ (Every 10 min keep-alive)
                          └─────────────┬─────────────┘
                                        │ GET /health
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       PROJECT VERONICA (FastAPI Web Service)                │
│                                                                             │
│  ┌───────────────────┐    ┌────────────────────┐    ┌────────────────────┐  │
│  │   ATS Scrapers    │───▶│   STAIR Matcher    │───▶│   Resume Tailor    │  │
│  │ (Greenhouse, etc) │    │  (Scores 0-100)    │    │ (Anti-Slop Engine) │  │
│  └───────────────────┘    └────────────────────┘    └─────────┬──────────┘  │
│                                                               │             │
│                                                               ▼             │
│  ┌───────────────────┐    ┌────────────────────┐    ┌────────────────────┐  │
│  │ Telegram (JARVIS) │◀───│ Multi-Provider LLM │◀───│  XeLaTeX Compiler  │  │
│  │ Discord / Webhook │    │ Groq ⮀ NVIDIA NIM  │    │   (PDF Artifact)   │  │
│  └───────────────────┘    └────────────────────┘    └────────────────────┘  │
│                                       │                                     │
│                                       ▼                                     │
│                         ┌───────────────────────────┐                       │
│                         │ SQLite Async (SQLAlchemy) │                       │
│                         └───────────────────────────┘                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚙️ Core Engineering Standards (Referenced from iyov-ai)

### 1. Release Gate Verification (`scripts/release_gate.sh`)
Every deployment and commit must pass the rigorous release gate:
- **Secret Containment**: Confirms no `.env` files are tracked in Git and `.dockerignore` excludes them.
- **Bytecode Compilation**: Validates all Python files compile cleanly (`python -m compileall`).
- **Comprehensive Unit & Integration Testing**: Executes `pytest -v` across all modules.
- **Live ASGI Smoke Testing**: Probes all core endpoints (`GET /`, `HEAD /`, `GET /health`, `HEAD /health`, `GET /settings`, `GET /trace`) to ensure HTTP 200 OK without unhandled exceptions.

### 2. Multi-Provider LLM Failover
The system dynamically handles rate limits, service degradations, and API quotas:
- **Primary**: Groq (`llama-3.3-70b-versatile` / `llama3-70b-8192`)
- **Secondary**: NVIDIA NIM (`meta/llama-3.1-70b-instruct`)
- **Heuristic Fallback**: High-performance local deterministic extractor ensures zero crashes even if both external APIs are unreachable.

### 3. Production Keep-Alive Topology (Render Free Tier)
Render's free web service spins down instances after 15 minutes of inbound inactivity. 
- **Endpoint**: `https://<app-name>.onrender.com/health` (Supports both `GET` and `HEAD` verbs).
- **External Cron**: Pinged every 10 minutes via [cron-job.org](https://cron-job.org).
- **Result**: Zero cost, zero spin-down latency, 24/7 continuous operation.

---

## 📂 Key Files & Responsibilities

| File / Directory | Purpose |
|------------------|---------|
| `app/main.py` | FastAPI application entry point, Jinja2 template views, health check |
| `app/core/models.py` | SQLAlchemy 2.0 async database models with `selectin` eager loading |
| `app/services/llm_failover.py` | Resilient LLM client with automatic failover between Groq and NVIDIA NIM |
| `app/services/resume_tailor.py` | Anti-slop prompt orchestrator, XeLaTeX builder, PDF generator |
| `app/services/stair_matcher.py` | Calibrated scoring engine (Skills, Title, Experience, Alignment) |
| `app/services/scrapers/` | High-throughput ATS extractors (Greenhouse, Lever, Ashby, etc.) |
| `scripts/release_gate.sh` | Automated pre-release quality gate and sanity verification |
| `Dockerfile` | Multi-stage image with XeLaTeX and curl healthcheck |
| `.dockerignore` | Build-context security exclusions |

