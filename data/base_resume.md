# Thigulla Meghraj Goud — Updated Resume (.NET Full-Stack & AI)

- **Live Deployed ATS**: [https://talentflow-6tgp.onrender.com](https://talentflow-6tgp.onrender.com)
- **GitHub Repository**: [https://github.com/MeghrajGoudThigulla/TalentFlow](https://github.com/MeghrajGoudThigulla/TalentFlow)

---

## 1. LaTeX Source Code (`resume.tex`)

```latex
\documentclass{resume}

\usepackage{fontspec}
\usepackage{hyperref}
\usepackage{enumitem}
\usepackage{tabularx}
\usepackage{needspace}

\setmainfont{Georgia}

\usepackage[left=0.50in,right=0.50in,top=0.45in,bottom=0.45in]{geometry}

\hypersetup{colorlinks=true,urlcolor=blue,linkcolor=blue}

\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}

\setlist[itemize]{leftmargin=1.25em,topsep=2.5pt,itemsep=1.5pt,parsep=0pt,partopsep=0pt}

\renewenvironment{rSection}[1]{
    \vspace{8pt}
    \noindent
    {\bfseries\MakeUppercase{#1}}
    \par
    \vspace{-3.5pt}
    \noindent\rule{\textwidth}{0.4pt}
    \par
    \vspace{4pt}
}{
    \vspace{3pt}
}

\name{Thigulla Meghraj Goud}

\address{
\href{https://api.whatsapp.com/send/?phone=917997221772}{+91 79972 21772}
\quad
\href{mailto:meghraj.thigulla@outlook.com}{meghraj.thigulla@outlook.com}
\quad
\href{https://www.linkedin.com/in/meghraj-goud-thigulla}{LinkedIn}
\quad
\href{https://meghraj-portfolio.web.app/}{Portfolio}
\quad
\href{https://github.com/MeghrajGoudThigulla}{GitHub}
\quad
\href{https://linktr.ee/meghraj_goud_thigulla}{Certificates}
}

\begin{document}
\sloppy

% =========================================================
% EXPERIENCE
% =========================================================

\begin{rSection}{EXPERIENCE}

\textbf{Senior AI Developer \& Full Stack Engineer}
\hfill July 2024 - Oct 2026 \\
Threshing Floor Group, Hyderabad
\hfill \href{https://tfgroup.ai/en}{tfgroup.ai}

\vspace{-2pt}

\begin{itemize}
    \item Delivered backend infrastructure of 286 endpoints, 61+ database models, and 30+ Alembic/Prisma migrations across multiple production products, owning schema design end to end. % METRIC: users served / uptime
    \item Shipped 80+ mobile screens and 96+ web interfaces with Flutter, React, and Next.js on FastAPI backends, partnering with design and product to deliver on schedule.
    \item Owned App Store / Play Store releases and deployment pipelines for 4+ Flutter apps (Employee Portal, HRMS, LMS, Care Navigator).
    \item Engineered PostgreSQL/Supabase data layers with Row-Level Security, Redis rate limiting, Celery webhook workers, and dual-store WebSocket sync.
    \item Deployed ML pipelines (OCR, embeddings) and third-party provider APIs into production FastAPI services.
    \item Partnered with executive stakeholders as technical consultant, converting ambiguous requirements into shippable milestones; directed knowledge transfer for 8 engineers.
\end{itemize}

\end{rSection}

% =========================================================
% SKILLS
% =========================================================
\begin{rSection}{SKILLS}

\vspace{-2pt}

\begin{tabularx}{\textwidth}{
    @{}
    >{\bfseries}p{1.6in}
    X
    @{}
}
Languages &
C\#, Python, Dart, JavaScript, TypeScript, C++, SQL \\

Backend &
ASP.NET Core, .NET Web API, Entity Framework Core, LINQ, MediatR, SignalR, FluentValidation, Serilog, MailKit, FastAPI, Flask, Express, Celery, SQLAlchemy, Alembic, Prisma \\

Frontend \& Mobile &
Flutter, React, Next.js, HTML5, CSS3, JavaScript (ES6+), Tailwind CSS, MUI \\

Databases &
SQL Server, SQLite, PostgreSQL, MySQL, MongoDB, Redis, Firestore, Supabase \\

Architecture &
Clean Architecture, CQRS, REST APIs, RBAC, JWT, SignalR, Concurrency Control, Transactional Outbox, Rate Limiting, Caching, Row-Level Security \\

AI/ML \& OCR &
ONNX Runtime, PaddleOCR, PyTesseract, Sentence Transformers, Embeddings, Model Gateway Services \\

DevOps \& Tooling &
Docker, Docker Compose, GitHub Actions, Render, NetArchTest, AWS EC2, nginx, systemd, Git, Visual Studio, VS Code, NuGet, xUnit \\
\end{tabularx}

\end{rSection}

% =========================================================
% PROJECTS
% =========================================================

\begin{rSection}{PROJECTS}

% ---------------- TALENTFLOW (.NET) ----------------

\Needspace{8\baselineskip}

\textbf{TalentFlow} -- Enterprise Applicant Tracking System \& Pipeline (Personal Project)
\hfill \href{https://talentflow-6tgp.onrender.com}{Live Demo} \quad \href{https://github.com/MeghrajGoudThigulla/TalentFlow}{GitHub} \\[-1pt]
\textit{Tech: C\#, .NET 8, ASP.NET Core, EF Core, SQL Server, MediatR, SignalR, Docker, Serilog, NetArchTest, xUnit}

\vspace{-2pt}

\begin{itemize}
    \item Architected a .NET 8 Web API with Clean Architecture and CQRS (MediatR), enforcing pipeline behaviors (Validation $\rightarrow$ Logging $\rightarrow$ Transaction $\rightarrow$ Audit); achieved \textbf{73.4\% test coverage} across \textbf{90 automated tests} (xUnit, NetArchTest, WebApplicationFactory).
    \item Implemented the \textbf{Transactional Outbox Pattern} with SQL Server atomic table claims (\texttt{UPDLOCK, READPAST}), exponential backoff, and deduplication keys, guaranteeing at-least-once candidate email delivery via MailKit.
    \item Designed \texttt{RowVersion} optimistic concurrency control resolving concurrent card movements with HTTP 409 Conflict; broadcast zero-latency Kanban pipeline updates across recruiter sessions via authenticated \textbf{SignalR} WebSocket groups.
    \item Hardened application security against OWASP API Top 10: resource-based authorization (IDOR prevention on candidate evaluations), fixed-window rate limiting, magic-byte file signature validation on CVs, and request correlation IDs with Serilog.
    \item Containerized multi-service stack with \textbf{Docker Compose} (API, SQL Server 2022, MailHog) and automated CI/CD via \textbf{GitHub Actions} with automated coverage gates, zero compiler warnings (\texttt{-warnaserror}), and continuous deployment to \textbf{Render}.
\end{itemize}

\vspace{3pt}

% ---------------- IYOV AI ----------------

\Needspace{8\baselineskip}

\textbf{IYOV AI} -- AI-Powered Workforce Management Ecosystem
\hfill \href{https://iyov.ai/}{iyov.ai} \\[-1pt]
\textit{Tech: Python, FastAPI, Flutter, Riverpod, GoRouter, Next.js, PostgreSQL, Redis, Firebase}

\vspace{-2pt}

\begin{itemize}
    \item Owned the India tax and compliance payroll module from scratch, translating complex statutory rules into automated payroll formulas. % METRIC: employees/batch size, processing time
    \item Streamlined payroll batches, document processing, and bulk worker notifications with Redis-backed job queues.
    \item Released 4+ companion Flutter apps (Employee Portal, HRMS, LMS, Care Navigator) to App Store / Play Store.
    \item Streamlined mobile build configurations and automated pipelines, shortening turnaround for critical hotfixes.
\end{itemize}

\vspace{3pt}

% ---------------- TFG SECUREBANKING ----------------

\Needspace{8\baselineskip}

\textbf{TFG SecureBanking} -- Digital Fintech Application
\hfill \href{https://tfgsecurebank.com/}{tfgsecurebank.com} \\[-1pt]
\textit{Tech: Python, FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis, WeasyPrint}

\vspace{-2pt}

\begin{itemize}
    \item Architected a multi-tenant FastAPI backend of 70 REST endpoints, routing between PostgreSQL/Supabase and legacy MySQL.
    \item Engineered a rules engine (openpyxl, xlcalculator) that executes credit validation matrices directly from Excel templates.
    \item Delivered tamper-proof loan agreement PDFs using WeasyPrint and Jinja2 templates.
\end{itemize}

\vspace{3pt}

% ---------------- TFGENAPI ----------------

\Needspace{8\baselineskip}

\textbf{TFGenAPI} -- Verification \& Custom API Platform
\hfill \href{https://tfgenapi.ai/}{tfgenapi.ai} \\[-1pt]
\textit{Tech: Next.js 16, Python, FastAPI, MongoDB, PyTesseract, Sentence Transformers}

\vspace{-2pt}

\begin{itemize}
    \item Owned the verification API platform end to end, from database design to cross-layer integration. % METRIC: docs verified, latency, accuracy
    \item Deployed an AI inference pipeline combining PyTesseract OCR with Sentence Transformers embeddings for document matching.
    \item Specialized in MongoDB (Motor) data modeling for high-throughput unstructured document ingestion and ML feature persistence.
    \item Executed asynchronous verification flows and webhook notifications with Celery/Redis task queues.
\end{itemize}

\vspace{3pt}

% ---------------- MEDICAL ADVISOR ----------------

\Needspace{7\baselineskip}

\textbf{Medical Advisor} -- Mission-Critical Healthcare API
\hfill \href{https://play.google.com/store/apps/details?id=com.tfg.medicaladvisor&pcampaignid=web_share}{Play Store} \\[-1pt]
\textit{Tech: Python, FastAPI, PostgreSQL, Redis, Firebase/GCP, Docker}

\vspace{-2pt}

\begin{itemize}
    \item Architected a FastAPI microservice secured with strict JWT authentication and Google Play Integrity nonces.
    \item Engineered an asynchronous dual-write pipeline syncing PostgreSQL transaction state to Firestore for real-time WebSockets.
    \item Directed knowledge transfer as technical lead, onboarding 8 engineers.
\end{itemize}

\vspace{3pt}

\textbf{Additional Projects:}
\textbf{DealsMart} (Flutter, FastAPI, PostgreSQL, RQ workers; delivered ACID cart mutations and idempotent payment reconciliation; pre-release);
\href{https://tfgroup.ai/en}{\textbf{TFG Corporate Website}} (Next.js, Flask; executed zero-downtime migration from legacy static site);
\href{https://groconnect.co.in/}{\textbf{GroConnect}} (PHP, Node.js; delivered client portal and AI training platform).

\end{rSection}

% =========================================================
% EDUCATION
% =========================================================

\begin{rSection}{EDUCATION}

\textbf{Bachelor of Technology in Information Technology}
\hfill 2020--2024 \\
Vignana Bharathi Institute of Technology (VBIT), Ghatkesar

\end{rSection}

% =========================================================
% CERTIFICATIONS
% =========================================================

\begin{rSection}{CERTIFICATIONS}

\vspace{-2pt}

\begin{itemize}
    \item \textbf{AWS Academy}: Cloud Foundations; Machine Learning Foundations; AI-ML Virtual Internship
    \item \textbf{Cisco}: Networking Essentials; Introduction to Cybersecurity; Cybersecurity Essentials
    \item \textbf{Fortinet}: Certified Fundamentals; Certified Associate in Cybersecurity; Network Security Associate Virtual Internship
    \item \textbf{Celonis}: Foundations; Academic Process Mining Fundamentals; Execution Management Consulting Program
\end{itemize}

\end{rSection}

\end{document}
```

---

## 2. Plain Text / Markdown Overview

### THIGULLA MEGHRAJ GOUD
**Contact**: [+91 79972 21772](https://api.whatsapp.com/send/?phone=917997221772) | [meghraj.thigulla@outlook.com](mailto:meghraj.thigulla@outlook.com)  
**Links**: [LinkedIn](https://www.linkedin.com/in/meghraj-goud-thigulla) | [Portfolio](https://meghraj-portfolio.web.app/) | [GitHub](https://github.com/MeghrajGoudThigulla) | [Certificates](https://linktr.ee/meghraj_goud_thigulla)

---

### EXPERIENCE
**Senior AI Developer & Full Stack Engineer** — Threshing Floor Group, Hyderabad *(July 2024 – Oct 2026)*
- Delivered backend infrastructure of 286 endpoints, 61+ database models, and 30+ Alembic/Prisma migrations across multiple production products, owning schema design end to end.
- Shipped 80+ mobile screens and 96+ web interfaces with Flutter, React, and Next.js on FastAPI backends, partnering with design and product to deliver on schedule.
- Owned App Store / Play Store releases and deployment pipelines for 4+ Flutter apps (Employee Portal, HRMS, LMS, Care Navigator).
- Engineered PostgreSQL/Supabase data layers with Row-Level Security, Redis rate limiting, Celery webhook workers, and dual-store WebSocket sync.
- Deployed ML pipelines (OCR, embeddings) and third-party provider APIs into production FastAPI services.
- Partnered with executive stakeholders as technical consultant, converting ambiguous requirements into shippable milestones; directed knowledge transfer for 8 engineers.

---

### SKILLS
- **Languages**: C#, Python, Dart, JavaScript, TypeScript, C++, SQL
- **Backend**: ASP.NET Core, .NET Web API, Entity Framework Core, LINQ, MediatR, SignalR, FluentValidation, Serilog, MailKit, FastAPI, Flask, Express, Celery, SQLAlchemy, Alembic, Prisma
- **Frontend & Mobile**: Flutter, React, Next.js, HTML5, CSS3, JavaScript (ES6+), Tailwind CSS, MUI
- **Databases**: SQL Server, SQLite, PostgreSQL, MySQL, MongoDB, Redis, Firestore, Supabase
- **Architecture**: Clean Architecture, CQRS, REST APIs, RBAC, JWT, SignalR, Concurrency Control, Transactional Outbox, Rate Limiting, Caching, Row-Level Security
- **AI/ML & OCR**: ONNX Runtime, PaddleOCR, PyTesseract, Sentence Transformers, Embeddings, Model Gateway Services
- **DevOps & Tooling**: Docker, Docker Compose, GitHub Actions, Render, NetArchTest, AWS EC2, nginx, systemd, Git, Visual Studio, VS Code, NuGet, xUnit

---

### PROJECTS

**1. TalentFlow — Enterprise Applicant Tracking System & Pipeline (Personal Project)**  
*Tech: C#, .NET 8, ASP.NET Core, EF Core, SQL Server, MediatR, SignalR, Docker, Serilog, NetArchTest, xUnit*  
- Architected a .NET 8 Web API with Clean Architecture and CQRS (MediatR), enforcing pipeline behaviors (Validation → Logging → Transaction → Audit); achieved **73.4% test coverage** across **90 automated tests** (xUnit, NetArchTest, WebApplicationFactory).
- Implemented the **Transactional Outbox Pattern** with SQL Server atomic table claims (`UPDLOCK, READPAST`), exponential backoff, and deduplication keys, guaranteeing at-least-once candidate email delivery via MailKit.
- Designed `RowVersion` optimistic concurrency control resolving concurrent card movements with HTTP 409 Conflict; broadcast zero-latency Kanban pipeline updates across recruiter sessions via authenticated **SignalR** WebSocket groups.
- Hardened application security against OWASP API Top 10: resource-based authorization (IDOR prevention on candidate evaluations), fixed-window rate limiting, magic-byte file signature validation on CVs, and request correlation IDs with Serilog.
- Containerized multi-service stack with **Docker Compose** (API, SQL Server 2022, MailHog) and automated CI/CD via **GitHub Actions** with automated coverage gates, zero compiler warnings (`-warnaserror`), and continuous deployment to **Render**.  
- **Live Demo**: [https://talentflow-6tgp.onrender.com](https://talentflow-6tgp.onrender.com) | **Code**: [https://github.com/MeghrajGoudThigulla/TalentFlow](https://github.com/MeghrajGoudThigulla/TalentFlow)

**2. IYOV AI — AI-Powered Workforce Management Ecosystem**  
*Tech: Python, FastAPI, Flutter, Riverpod, GoRouter, Next.js, PostgreSQL, Redis, Firebase*  
- Owned the India tax and compliance payroll module from scratch, translating complex statutory rules into automated payroll formulas.
- Streamlined payroll batches, document processing, and bulk worker notifications with Redis-backed job queues.
- Released 4+ companion Flutter apps (Employee Portal, HRMS, LMS, Care Navigator) to App Store / Play Store.
- Streamlined mobile build configurations and automated pipelines, shortening turnaround for critical hotfixes.

**3. TFG SecureBanking — Digital Fintech Application**  
*Tech: Python, FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis, WeasyPrint*  
- Architected a multi-tenant FastAPI backend of 70 REST endpoints, routing between PostgreSQL/Supabase and legacy MySQL.
- Engineered a rules engine (openpyxl, xlcalculator) that executes credit validation matrices directly from Excel templates.
- Delivered tamper-proof loan agreement PDFs using WeasyPrint and Jinja2 templates.

**4. TFGenAPI — Verification & Custom API Platform**  
*Tech: Next.js 16, Python, FastAPI, MongoDB, PyTesseract, Sentence Transformers*  
- Owned the verification API platform end to end, from database design to cross-layer integration.
- Deployed an AI inference pipeline combining PyTesseract OCR with Sentence Transformers embeddings for document matching.
- Specialized in MongoDB (Motor) data modeling for high-throughput unstructured document ingestion and ML feature persistence.
- Executed asynchronous verification flows and webhook notifications with Celery/Redis task queues.

**5. Medical Advisor — Mission-Critical Healthcare API**  
*Tech: Python, FastAPI, PostgreSQL, Redis, Firebase/GCP, Docker*  
- Architected a FastAPI microservice secured with strict JWT authentication and Google Play Integrity nonces.
- Engineered an asynchronous dual-write pipeline syncing PostgreSQL transaction state to Firestore for real-time WebSockets.
- Directed knowledge transfer as technical lead, onboarding 8 engineers.

**Additional Projects:**  
- **DealsMart** (Flutter, FastAPI, PostgreSQL, RQ workers; delivered ACID cart mutations and idempotent payment reconciliation; pre-release)  
- [**TFG Corporate Website**](https://tfgroup.ai/en) (Next.js, Flask; executed zero-downtime migration from legacy static site)  
- [**GroConnect**](https://groconnect.co.in/) (PHP, Node.js; delivered client portal and AI training platform)

---

### EDUCATION
**Bachelor of Technology in Information Technology** *(2020 – 2024)*  
Vignana Bharathi Institute of Technology (VBIT), Ghatkesar

---

### CERTIFICATIONS
- **AWS Academy**: Cloud Foundations; Machine Learning Foundations; AI-ML Virtual Internship
- **Cisco**: Networking Essentials; Introduction to Cybersecurity; Cybersecurity Essentials
- **Fortinet**: Certified Fundamentals; Certified Associate in Cybersecurity; Network Security Associate Virtual Internship
- **Celonis**: Foundations; Academic Process Mining Fundamentals; Execution Management Consulting Program
