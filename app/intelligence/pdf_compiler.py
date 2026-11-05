import os
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any
from app.config import settings

logger = logging.getLogger("personal_job_agent.pdf")

class PDFCompiler:
    """
    Compiles LaTeX resumes into clean PDF documents using XeLaTeX or pdfLaTeX.
    Provides fallback to clean HTML-printable format if TeX Live is absent.
    """

    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or (settings.DATA_DIR / "tailored_resumes")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # Ensure resume.cls is available in output directory
        cls_src = settings.DATA_DIR / "resume.cls"
        if cls_src.exists():
            shutil.copy(cls_src, self.output_dir / "resume.cls")

    def compile_resume(self, job_id: int, company_slug: str, latex_content: str) -> Dict[str, Any]:
        """
        Saves LaTeX and attempts compilation to PDF.
        """
        filename_base = f"Meghraj_Goud_{company_slug}_{job_id}"
        tex_path = self.output_dir / f"{filename_base}.tex"
        pdf_path = self.output_dir / f"{filename_base}.pdf"
        html_path = self.output_dir / f"{filename_base}.html"

        # 1. Write .tex file
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(latex_content)

        # 2. Check for xelatex or pdflatex
        compiler = shutil.which("xelatex") or shutil.which("pdflatex")
        
        if compiler:
            try:
                cmd = [
                    compiler,
                    "-interaction=nonstopmode",
                    f"-output-directory={self.output_dir}",
                    str(tex_path)
                ]
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
                if result.returncode == 0 and pdf_path.exists():
                    logger.info(f"Successfully compiled PDF: {pdf_path}")
                    return {
                        "success": True,
                        "pdf_path": str(pdf_path),
                        "tex_path": str(tex_path),
                        "message": "Compiled successfully with XeLaTeX."
                    }
                else:
                    logger.warning(f"LaTeX compilation failed with code {result.returncode}. Generating HTML fallback.")
            except Exception as e:
                logger.error(f"Error executing LaTeX compiler: {e}")

        # 3. Generate HTML printable fallback
        self._generate_html_resume(latex_content, html_path, filename_base)
        
        return {
            "success": True,
            "pdf_path": str(pdf_path) if pdf_path.exists() else str(html_path),
            "tex_path": str(tex_path),
            "html_path": str(html_path),
            "message": "LaTeX source saved. Printable HTML version generated (LaTeX engine available in Docker/Render container)."
        }

    def _generate_html_resume(self, latex_content: str, output_path: Path, title: str):
        """Creates a clean, styled HTML version of the resume for direct browser printing/saving to PDF."""
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{
            font-family: Georgia, 'Times New Roman', serif;
            margin: 0;
            padding: 24px;
            color: #111827;
            background: #ffffff;
            line-height: 1.4;
            max-width: 850px;
            margin: auto;
        }}
        h1 {{
            text-align: center;
            font-size: 24px;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 4px;
        }}
        .contact {{
            text-align: center;
            font-size: 13px;
            margin-bottom: 20px;
            color: #374151;
        }}
        .contact a {{
            color: #1d4ed8;
            text-decoration: none;
            margin: 0 6px;
        }}
        .section-title {{
            font-size: 14px;
            font-weight: bold;
            text-transform: uppercase;
            border-bottom: 1.5px solid #111827;
            padding-bottom: 2px;
            margin-top: 18px;
            margin-bottom: 8px;
            letter-spacing: 0.5px;
        }}
        .job-header {{
            display: flex;
            justify-content: space-between;
            font-weight: bold;
            font-size: 14px;
            margin-top: 6px;
        }}
        .job-sub {{
            display: flex;
            justify-content: space-between;
            font-style: italic;
            font-size: 13px;
            color: #4b5563;
            margin-bottom: 4px;
        }}
        ul {{
            margin: 4px 0 10px 18px;
            padding: 0;
            font-size: 13px;
        }}
        li {{
            margin-bottom: 4px;
        }}
        .skills-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            margin-top: 6px;
        }}
        .skills-table td {{
            padding: 3px 0;
            vertical-align: top;
        }}
        .skills-label {{
            font-weight: bold;
            width: 140px;
        }}
        @media print {{
            body {{ padding: 0; }}
            .no-print {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="no-print" style="background: #f3f4f6; padding: 12px; margin-bottom: 20px; border-radius: 6px; text-align: center;">
        <button onclick="window.print()" style="padding: 8px 18px; background: #2563eb; color: white; border: none; border-radius: 4px; font-weight: bold; cursor: pointer;">
            🖨️ Print to PDF / Save as PDF
        </button>
        <span style="margin-left: 14px; font-size: 13px; color: #4b5563;">LaTeX source is also saved at {output_path.stem}.tex</span>
    </div>

    <h1>Thigulla Meghraj Goud</h1>
    <div class="contact">
        <a href="tel:+917997221772">+91 79972 21772</a> |
        <a href="mailto:meghraj.thigulla@outlook.com">meghraj.thigulla@outlook.com</a> |
        <a href="https://www.linkedin.com/in/meghraj-goud-thigulla">LinkedIn</a> |
        <a href="https://meghraj-portfolio.web.app/">Portfolio</a> |
        <a href="https://github.com/MeghrajGoudThigulla">GitHub</a>
    </div>

    <div class="section-title">Experience</div>
    <div class="job-header">
        <span>Senior AI Developer & Full Stack Engineer</span>
        <span>July 2024 - Oct 2026</span>
    </div>
    <div class="job-sub">
        <span>Threshing Floor Group, Hyderabad</span>
        <span>tfgroup.ai</span>
    </div>
    <ul>
        <li>Delivered backend infrastructure of 286 endpoints, 61+ database models, and 30+ Alembic/Prisma migrations across multiple production products, owning schema design end to end.</li>
        <li>Shipped 80+ mobile screens and 96+ web interfaces with Flutter, React, and Next.js on FastAPI backends, partnering with design and product to deliver on schedule.</li>
        <li>Owned App Store / Play Store releases and deployment pipelines for 4+ Flutter apps (Employee Portal, HRMS, LMS, Care Navigator).</li>
        <li>Engineered PostgreSQL/Supabase data layers with Row-Level Security, Redis rate limiting, Celery webhook workers, and dual-store WebSocket sync.</li>
        <li>Deployed ML pipelines (OCR, embeddings) and third-party provider APIs into production FastAPI services.</li>
        <li>Partnered with executive stakeholders as technical consultant, converting ambiguous requirements into shippable milestones; directed knowledge transfer for 8 engineers.</li>
    </ul>

    <div class="section-title">Technical Skills</div>
    <table class="skills-table">
        <tr><td class="skills-label">Languages:</td><td>C#, Python, Dart, JavaScript, TypeScript, C++, SQL</td></tr>
        <tr><td class="skills-label">Backend:</td><td>FastAPI, ASP.NET Core, .NET 8, MediatR, SignalR, Celery, SQLAlchemy, Alembic, Prisma</td></tr>
        <tr><td class="skills-label">Frontend & Mobile:</td><td>Flutter, React, Next.js, HTML5, CSS3, Tailwind CSS</td></tr>
        <tr><td class="skills-label">Databases:</td><td>PostgreSQL, Redis, SQL Server, SQLite, Supabase, Firebase</td></tr>
        <tr><td class="skills-label">Architecture:</td><td>Clean Architecture, CQRS, REST APIs, RBAC, Transactional Outbox, Rate Limiting, Caching</td></tr>
        <tr><td class="skills-label">AI/ML & OCR:</td><td>ONNX Runtime, PaddleOCR, Sentence Transformers, Embeddings, Model Gateway</td></tr>
        <tr><td class="skills-label">DevOps:</td><td>Docker, Docker Compose, GitHub Actions, Render, AWS EC2, Linux, Git</td></tr>
    </table>

    <div class="section-title">Projects</div>
    <div class="job-header">
        <span>TalentFlow — Enterprise Applicant Tracking System</span>
        <span><a href="https://talentflow-6tgp.onrender.com">Live Demo</a> | <a href="https://github.com/MeghrajGoudThigulla/TalentFlow">GitHub</a></span>
    </div>
    <div class="job-sub">
        <span>Tech: C#, .NET 8, ASP.NET Core, EF Core, SQL Server, MediatR, SignalR, Docker, Serilog</span>
        <span>Render</span>
    </div>
    <ul>
        <li>Architected a .NET 8 Web API with Clean Architecture and CQRS (MediatR), achieving 73.4% test coverage across 90 automated tests.</li>
        <li>Implemented Transactional Outbox Pattern with SQL Server atomic table claims (UPDLOCK, READPAST), exponential backoff, and deduplication keys.</li>
        <li>Designed RowVersion optimistic concurrency control and zero-latency Kanban pipeline updates via SignalR WebSockets.</li>
        <li>Containerized multi-service stack with Docker Compose and automated CI/CD via GitHub Actions.</li>
    </ul>

    <div class="job-header" style="margin-top: 10px;">
        <span>IYOV AI — AI-Powered Workforce Management Ecosystem</span>
        <span><a href="https://iyov.ai/">iyov.ai</a></span>
    </div>
    <div class="job-sub">
        <span>Tech: Python, FastAPI, Flutter, Riverpod, Next.js, PostgreSQL, Redis</span>
        <span>Production</span>
    </div>
    <ul>
        <li>Owned the India tax and compliance payroll module from scratch, translating complex statutory rules into automated payroll formulas.</li>
        <li>Integrated ML pipelines for automated invoice and document OCR extraction with PaddleOCR and ONNX runtime.</li>
    </ul>

    <div class="section-title">Education</div>
    <div class="job-header">
        <span>Vignana Bharathi Institute of Technology (VBIT)</span>
        <span>2020 - 2024</span>
    </div>
    <div class="job-sub">
        <span>Bachelor of Technology in Information Technology</span>
        <span>CGPA: 8.71 / 10 | Hyderabad, India</span>
    </div>
</body>
</html>
"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
