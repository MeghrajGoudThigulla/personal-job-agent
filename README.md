# 🎯 Personal Job Agent

> **Autonomous Job Scout, Structure-Aware (STAIR) Matcher & Anti-Slop Resume Tailoring Agent**  
> Custom-engineered for **Thigulla Meghraj Goud** (Senior AI Developer & Full Stack Engineer).

[![CI Test Suite](https://github.com/MeghrajGoudThigulla/personal-job-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/MeghrajGoudThigulla/personal-job-agent/actions)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-blue.svg)](#-docker-deployment)
[![Render Ready](https://img.shields.io/badge/Render-Blueprint-46E3B7.svg)](#-deploying-to-render)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ⚡ Overview

**Personal Job Agent** is an end-to-end, automated career acceleration engine. It continuously monitors target applicant tracking systems (Ashby, Greenhouse, Lever, Workday) and remote job feeds, analyzes job postings against Meghraj's actual verified technical metrics using **Structure-Aware Information Retrieval (STAIR)**, eliminates AI buzzwords via the **Slop Reduction System**, and dispatches instant alerts via **Telegram** and **Discord** the minute high-match roles appear.

```
                                  ┌───────────────────────────┐
                                  │   Target Job Sources      │
                                  │  • Ashby, Greenhouse,     │
                                  │    Lever Public APIs      │
                                  │  • RemoteOK, Jobicy,      │
                                  │    Remotive, Arbeitnow    │
                                  │  • 121 Tailored ATS Dorks │
                                  │  • JobSpy (LinkedIn/Glass)│
                                  └─────────────┬─────────────┘
                                                │
                                                ▼
┌──────────────────────────┐      ┌───────────────────────────┐
│ Candidate Profile & Data │ ───► │  STAIR Matcher & Ranker   │
│ • Base LaTeX Resume      │      │  (Structure-Aware Section │
│ • 11 P1/P2/P3 Roles      │      │   Matching & Seniority)   │
│ • Real-World Metrics     │      └─────────────┬─────────────┘
└──────────────────────────┘                    │ (Score >= 70%)
                                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            AUTOMATION ENGINE                                │
│                                                                             │
│  ┌─────────────────────────┐   ┌──────────────────────┐   ┌───────────────┐ │
│  │ Anti-Slop Resume Tailor │   │ Cold Email & 4MM Gen │   │ Real-Time     │ │
│  │ • Reorders Tech Stack   │   │ • HR / Recruiter     │   │ Alerting      │ │
│  │ • Concrete Verbs        │   │ • Hiring Manager     │   │ • Telegram    │ │
│  │ • XeLaTeX PDF Compile   │   │ • MPM 4MM LinkedIn   │   │ • Discord     │ │
│  └─────────────────────────┘   └──────────────────────┘   └───────────────┘ │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 FastAPI Control Center & Web Dashboard                      │
│                 (Search, Filter, 1-Click Tailor & Download)                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Key Capabilities

### 1. 🔍 Autonomous Multi-Source Job Scouring
- **Direct ATS API Scraper**: Directly monitors public posting APIs for **Ashby**, **Greenhouse**, and **Lever** across target companies (Linear, PostHog, Supabase, Raycast, Cal.com, Anthropic, Databricks, Stripe, Figma, Vercel, etc.).
- **Live Remote API Scrapers**: Continuously streams newly posted software roles from Jobicy, RemoteOK, Remotive, and Arbeitnow.
- **ATS Dorks Engine**: Automates the **121 targeted boolean queries** across 11 roles (Backend, AI Backend, Product, Full Stack, SDE II, Platform, Applied AI, Mobile, Tech Solutions, Document AI, Forward Deployed) targeting Ashby, Lever, Greenhouse, Workday, SmartRecruiters, iCIMS, BambooHR, Jobvite, JazzHR, and Workable.
- **JobSpy Integration**: Direct scraping of Indeed and Glassdoor with country and recency filters.

### 2. 🧠 STAIR Structure-Aware Matcher (`2609.03874v2.pdf`)
Rather than relying on flat keyword search, the system implements hierarchical structure-aware retrieval inspired by IBM STAIR:
- **Stack Alignment**: Evaluates core languages, backend frameworks, mobile/frontend, databases, and DevOps capabilities against Meghraj's real stack.
- **Seniority & Negative Filters**: Automatically filters out internships, freshers, and 8+ YOE requirements, targeting the sweet spot (1-4 YOE, Engineer I/II, SDE II).
- **Location & Feasibility**: Prioritizes Remote India, Remote APAC, Hyderabad, and Bengaluru while filtering restricted national clearances.

### 3. ✍️ Anti-Slop Tailored Resume & Outreach Engine (`slop-reduct.md`)
- **Zero AI Buzzwords**: Strict anti-slop scanner prohibits vague corporate fluff (`seamless`, `robust`, `cutting-edge`, `game-changing`, `unlock`, `leverage`, `delve`, `tapestry`, `innovative`).
- **Preserved Engineering Metrics**: Retains Meghraj's actual verified metrics:
  - *286 endpoints, 61+ database models, 30+ Alembic/Prisma migrations*
  - *80+ mobile screens, 96+ web interfaces (Flutter, React, Next.js, FastAPI)*
  - *TalentFlow: .NET 8, Clean Architecture, CQRS, Outbox pattern, 73.4% test coverage across 90 tests*
  - *IYOV AI: FastAPI statutory payroll module, OCR & embeddings*
- **Native LaTeX PDF Compilation**: Compiles the customized `.tex` file into a PDF using XeLaTeX.
- **MPM Cold Outreach**: Generates clean cold emails for recruiters and hiring managers (with zero bold formatting in body) and the 4-Message LinkedIn networking sequence.

### 4. ⚡ Instant Real-Time Notifications
When a job with a match score $\ge 70\%$ is discovered:
- **Telegram Bot**: Pushes instant alert with role, company, match score, role tier, matched stack, direct apply link, and dashboard deep link.
- **Discord Webhook**: Sends color-coded rich embed card (Green for $\ge 85\%$, Blue for $\ge 70\%$).
- **Slack / Email**: Configurable incoming webhook and SMTP alerts.

### 5. 🤖 Multi-LLM Provider Architecture
- **Groq API**: Lightning-fast inference via `llama-3.3-70b-versatile` or `deepseek-r1-distill-llama-70b`.
- **NVIDIA NIM API**: High-capacity enterprise reasoning with `nvidia/nemotron-3-ultra-550b-a55b` or `meta/llama-3.1-70b-instruct`.
- **Intelligent Heuristic Fallback**: Built-in deterministic generator so the system functions even without API keys or during rate limits.

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| **Backend & REST API** | Python 3.12, FastAPI, Uvicorn |
| **Database & ORM** | SQLite, SQLAlchemy 2.0 (asyncio), aiosqlite |
| **Scheduler** | APScheduler (AsyncIOScheduler) |
| **Scrapers & Network** | HTTPX, BeautifulSoup4, python-jobspy, curl-cffi |
| **Resume Engine** | XeLaTeX, TeX Live, custom `resume.cls` |
| **Web UI** | Jinja2, Tailwind CSS, FontAwesome |
| **Testing** | Pytest, Pytest-AsyncIO |
| **Deployment** | Docker (multi-stage), Render Blueprint (`render.yaml`) |

---

## 🏃 Quick Start (Local Development)

### 1. Clone the repository
```bash
git clone https://github.com/MeghrajGoudThigulla/personal-job-agent.git
cd personal-job-agent
```

### 2. Create and activate a virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure environment variables
Copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```
Key configuration items:
- `GROQ_API_KEY`: Your Groq API key
- `NVIDIA_NIM_API_KEY`: Your NVIDIA NIM key (e.g. for `nvidia/nemotron-3-ultra-550b-a55b`)
- `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID`: For instant Telegram push alerts
- `DISCORD_WEBHOOK_URL`: For Discord channel alerts

### 4. Run the test suite
```bash
pytest -v
```

### 5. Start the application
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Open your browser at **`http://localhost:8000`** to access the dashboard!

---

## 🐳 Docker Deployment

The application includes a `Dockerfile` with minimal TeX Live and XeLaTeX pre-installed for native PDF resume compilation.

### Run with Docker Compose:
```bash
docker compose up --build -d
```
Access the dashboard at `http://localhost:8000`.

### Run standalone Docker container:
```bash
docker build -t personal-job-agent .
docker run -p 8000:8000 --env-file .env -v $(pwd)/data:/app/data personal-job-agent
```

---

## ☁️ 100% Free Deployment Options

You do **not** need a paid Render account. The project supports three 100% free hosting paths:

### Option A: Render Free Tier ($0/month, No Credit Card Required)
The `render.yaml` blueprint is configured for **Render's Free Tier** (`plan: free`).

1. Log in to [Render](https://render.com).
2. Click **New +** -> **Blueprint**.
3. Select `MeghrajGoudThigulla/personal-job-agent`.
4. Render will read `render.yaml` and set it up as a **Free Web Service** with `healthCheckPath: /health/live`.
5. Set your secret environment variables:
   - `APP_PASSWORD` (minimum 12 characters)
   - `SESSION_SECRET` (at least 32 random characters)
   - `DATABASE_URL` (Supabase Postgres connection pooler URL)
   - `GROQ_API_KEY`
   - `NVIDIA_NIM_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
6. Click **Apply Blueprint**!

> [!IMPORTANT]
> **Production Database Requirement (Supabase Postgres)**:
> In production on Render, you must configure `DATABASE_URL` with your **Supabase IPv4 Connection Pooler** (e.g. `postgresql+asyncpg://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres`).
> Do **not** use the direct `db.*.supabase.co` hostname because it resolves to IPv6-only addresses which Render cannot route. The connection pooler statement cache setting (`statement_cache_size=0`) is handled automatically by the application.
>
> If you choose to use SQLite on Render instead of Supabase, you must mount a **Persistent Disk** at `/app/data` (Render Dashboard -> Service -> Disks -> Add Disk -> Mount Path: `/app/data`), otherwise data and database files will be wiped on every container restart.

#### Database Migrations:
Database schema migrations run automatically on application startup via `init_db()`. You can also execute migrations manually at any time:
```bash
alembic upgrade head
```

#### Environment Variables Reference:
| Variable | Description | Default / Required |
| --- | --- | --- |
| `ENV` | Environment mode (`production` or `development`) | `development` |
| `APP_PASSWORD` | Access password for UI and API | Required in production (≥12 chars) |
| `SESSION_SECRET` | Secret key for signed, tamper-proof session cookies | Required in production (≥32 bytes) |
| `DATABASE_URL` | SQLAlchemy database URL (AsyncPG / SQLite) | `sqlite+aiosqlite:///data/jobs.db` |
| `PORT` | HTTP server port | `8000` |
| `SCHEDULER_ENABLED` | Enable autonomous APScheduler background jobs | `true` |
| `SCRAPE_INTERVAL_MINUTES` | Frequency of job discovery cycles | `60` |
| `MIN_MATCH_SCORE_NOTIFY` | Minimum STAIR match score (0-100) to trigger alerts | `70` |
| `MAX_JOB_AGE_DAYS` | Freshness cutoff gate: discard jobs posted older than N days | `7` |
| `DATA_RETENTION_DAYS` | Auto-cleanup retention period for jobs and applications | `60` |
| `SEEN_RETENTION_DAYS` | Persistent deduplication history retention for seen jobs | `365` |
| `AUTO_TAILOR_HIGH_MATCH` | Automatically generate tailored resumes & outreach | `true` |
| `LLM_PROVIDER` | LLM router provider (`auto`, `groq`, `nvidia`) | `auto` |
| `GROQ_API_KEY` | Groq Cloud API Key | Optional |
| `GROQ_MODEL` | Groq Model Name | `llama-3.3-70b-versatile` |
| `NVIDIA_NIM_API_KEY` | NVIDIA NIM Cloud API Key | Optional |
| `NVIDIA_NIM_MODEL` | NVIDIA NIM Model Name | `nvidia/nemotron-3-ultra-550b-a55b` |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token for push alerts | Optional |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID for push alerts | Optional |
| `DISCORD_WEBHOOK_URL` | Discord Channel Webhook URL | Optional |
| `SLACK_WEBHOOK_URL` | Slack Channel Webhook URL | Optional |
| `SMTP_HOST` | Outgoing SMTP server address | Optional |
| `SMTP_PORT` | Outgoing SMTP server port | `587` |
| `SMTP_USER` | SMTP username | Optional |
| `SMTP_PASS` | SMTP password | Optional |
| `SMTP_TO` | Target recipient email address | Optional (empty default) |

7. *(Optional Tip)*: Render's free tier sleeps after 15 minutes of inactivity. To keep your job hunter running continuously 24/7 for free:
   - Create a free account on [cron-job.org](https://cron-job.org) or [UptimeRobot](https://uptimerobot.com).
   - Set up a free monitor to ping your Render URL's `/health/live` endpoint every 10 minutes (e.g. `https://personal-job-agent.onrender.com/health/live`).

---

### Option B: Run 24/7 in Background on Your Local Linux Machine ($0)
Since you are on Linux, you can run the agent locally in the background without needing cloud hosting:

#### 1-Click Background Start:
```bash
./scripts/start_local.sh
```
This runs the agent in the background, logs output to `app.log`, and keeps it running even when you close the terminal.

#### Auto-Start on Boot (Systemd User Service):
```bash
mkdir -p ~/.config/systemd/user
cp scripts/personal-job-agent.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now personal-job-agent
```
The agent will automatically start whenever your machine is powered on.

---

### Option C: Koyeb / Hugging Face Spaces (Free Cloud Alternatives)
- **Koyeb Free Tier**: Supports Docker containers with 512MB RAM and does not spin down.
- **Hugging Face Spaces**: Select **Docker** space (100% free, 16GB RAM, 2 vCPUs, never sleeps). Connect your GitHub repo and it runs 24/7.

---

## 📱 Setting Up Instant Alerts

### Telegram Bot Alerts (Recommended):
1. Open Telegram and search for `@BotFather`.
2. Send `/newbot`, follow prompts, and copy the **Bot Token**.
3. Search for `@userinfobot` in Telegram and click Start to get your **Chat ID**.
4. In the Personal Job Agent Settings page (or `.env`), set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
5. The moment a job matching $\ge 70\%$ is found, you receive an immediate notification with direct links.

### Discord Webhook Alerts:
1. In Discord, go to **Server Settings** -> **Integrations** -> **Webhooks** -> **New Webhook**.
2. Select your channel, copy the **Webhook URL**, and paste it into Settings.

---

## 📁 Repository Structure

```
personal-job-agent/
├── .github/workflows/ci.yml       # Automated CI test suite
├── app/
│   ├── api/                       # REST API (Jobs, Tailor, Scraper, Settings, Trace)
│   ├── core/                      # Async SQLite DB, Models, APScheduler, Audit Trace
│   ├── intelligence/              # STAIR Matcher, Resume Tailor, Outreach Gen, Anti-Slop, PDF Compiler, LLM
│   ├── notifiers/                 # Telegram, Discord, Slack, Email dispatchers
│   ├── scrapers/                  # Direct ATS (Ashby/GH/Lever), Remote boards, ATS Dorks, JobSpy
│   ├── templates/                 # Clean, modern Tailwind CSS dashboard & views
│   ├── config.py                  # Pydantic v2 application settings
│   └── main.py                    # FastAPI application entrypoint & lifespan
├── data/                          # Knowledge base & input assets
│   ├── base_resume.tex            # Meghraj's source LaTeX resume
│   ├── base_resume.md             # Base Markdown resume
│   ├── candidate_profile.json     # Verified metrics, skills & preferences
│   ├── personalized_queries.json  # 11 roles with 121 tailored ATS boolean dorks
│   ├── company_targets.json       # Target companies & ATS tokens
│   ├── cold_outreach_templates.json # MPM cheat sheet templates (HR, HM, 4MM)
│   ├── anti_slop_rules.json       # Slop Reduction System rules & buzzwords
│   └── resume.cls                 # LaTeX class file
├── tests/                         # Pytest test suite
├── Dockerfile                     # Multi-stage Docker build with XeLaTeX
├── docker-compose.yml             # Local Docker Compose service
├── render.yaml                    # Native Render Blueprint
├── requirements.txt               # Production Python dependencies
├── .env.example                   # Environment variable template
└── README.md                      # Complete system documentation
```

---

## 📄 License

MIT License. Engineered with pride for **Thigulla Meghraj Goud**.
