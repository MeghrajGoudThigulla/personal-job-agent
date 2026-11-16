"""
Resume Variant Manager & Specialized LaTeX Engine.
Provides 7 distinct, authentic resume variants for Meghraj Goud Thigulla,
allowing automatic dispatch of the most targeted resume directly to Telegram and recruiters.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.config import settings
from app.intelligence.pdf_compiler import PDFCompiler

logger = logging.getLogger("personal_job_agent.intelligence.variants")

VARIANTS_METADATA: Dict[str, Dict[str, Any]] = {
    "base": {
        "slug": "base",
        "headline": "Senior AI Developer & Full Stack Engineer | Python, FastAPI, Flutter, Next.js",
        "target_archetypes": ["General Software Engineer", "Full Stack AI Developer", "Founding Engineer"],
        "lead_focus": "Balanced end-to-end delivery: FastAPI backends, Flutter mobile, and Next.js platforms.",
        "skills_order": ["Languages", "Backend", "Frontend", "Mobile", "Databases", "Architecture", "AI/ML", "DevOps"],
    },
    "backend": {
        "slug": "backend",
        "headline": "Backend Developer | Python, FastAPI, PostgreSQL, Celery, Redis",
        "target_archetypes": ["Backend Engineer", "Python Engineer", "API Platform Engineer", "Distributed Systems"],
        "lead_focus": "High-throughput REST APIs, Celery/Redis workers, PostgreSQL schema migrations, and clean service boundaries.",
        "skills_order": ["Backend", "Languages", "Databases", "Architecture", "AI/ML", "DevOps", "Frontend", "Mobile"],
    },
    "ai": {
        "slug": "ai",
        "headline": "AI/ML Engineer | Applied AI, OCR, Embeddings, FastAPI",
        "target_archetypes": ["AI Engineer", "ML Engineer", "Computer Vision / OCR", "Applied AI Engineer"],
        "lead_focus": "PaddleOCR ONNX Runtime pipelines, BGE-M3 embeddings, document taxonomy extraction, and model serving.",
        "skills_order": ["AI/ML", "Languages", "Backend", "Databases", "DevOps", "Architecture", "Frontend", "Mobile"],
    },
    "mobile": {
        "slug": "mobile",
        "headline": "Flutter & Mobile Developer | Flutter, Dart, Firebase, FastAPI",
        "target_archetypes": ["Mobile Developer", "Flutter Engineer", "Android/iOS Developer", "Cross-Platform Engineer"],
        "lead_focus": "Flutter apps, Riverpod state management, App Store/Play Store submissions, and mobile-backend sync.",
        "skills_order": ["Mobile", "Languages", "Backend", "Databases", "DevOps", "Architecture", "Frontend", "AI/ML"],
    },
    "fullstack": {
        "slug": "fullstack",
        "headline": "Full Stack Engineer & AI Developer | React, Next.js, FastAPI, Flutter",
        "target_archetypes": ["Full Stack Engineer", "Web & Mobile Developer", "Product Engineer"],
        "lead_focus": "React & Next.js frontend interfaces paired with high-performance FastAPI backends and Flutter apps.",
        "skills_order": ["Frontend", "Backend", "Languages", "Mobile", "Databases", "Architecture", "AI/ML", "DevOps"],
    },
    "frontend": {
        "slug": "frontend",
        "headline": "Frontend Developer | React, Next.js, TypeScript, Flutter Web",
        "target_archetypes": ["Frontend Engineer", "React Developer", "UI/UX Engineer", "Web Application Developer"],
        "lead_focus": "Modern Next.js App Router, TypeScript, React components, Tailwind CSS, and responsive interfaces.",
        "skills_order": ["Frontend", "Languages", "Backend", "Mobile", "DevOps", "Databases", "Architecture", "AI/ML"],
    },
    "consulting": {
        "slug": "consulting",
        "headline": "Technology Consultant & Senior Engineer | Architecture, Delivery, Stakeholder Management",
        "target_archetypes": ["Solutions Architect", "Technical Consultant", "Staff Engineer", "Engineering Lead"],
        "lead_focus": "Systems architecture, stakeholder requirement translation, engineer mentorship, and production delivery.",
        "skills_order": ["Architecture", "Backend", "Databases", "AI/ML", "Languages", "DevOps", "Frontend", "Mobile"],
    },
}


class ResumeVariantManager:
    """Manages generation, compilation, and selection of targeted resume variants."""

    def __init__(self, base_tex_path: Optional[Path] = None):
        self.base_tex_path = base_tex_path or settings.BASE_RESUME_TEX
        self.pdf_compiler = PDFCompiler()

    def _read_master_template(self) -> str:
        """Reads master LaTeX template with fallback to base resume."""
        if self.base_tex_path.exists():
            try:
                return self.base_tex_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.error(f"Error reading master template {self.base_tex_path}: {e}")
        return ""

    def get_all_variants(self) -> List[Dict[str, Any]]:
        """Returns metadata for all 7 resume variants."""
        return list(VARIANTS_METADATA.values())

    def select_best_variant(
        self,
        title: str = "",
        role_category: str = "",
        description: str = "",
        matched_skills: Optional[List[str]] = None,
    ) -> str:
        """
        Deterministically selects the most relevant resume variant
        based on role title, category, description keywords, and matched capabilities.
        """
        t = f"{title} {role_category}".lower()
        desc = description.lower()[:2000]
        skills = [s.lower() for s in (matched_skills or [])]

        # 1. Mobile & Flutter
        if any(k in t for k in ["flutter", "mobile", "android", "ios", "react native", "dart"]):
            return "mobile"

        # 2. AI / ML / Vision / NLP / OCR
        if any(k in t for k in ["ai", "ml", "machine learning", "deep learning", "nlp", "ocr", "computer vision", "llm", "rag"]):
            return "ai"
        if any(s in skills for s in ["paddleocr", "embeddings", "onnx", "sentence-transformers", "ocr", "rag"]):
            if "backend" not in t and "full stack" not in t:
                return "ai"

        # 3. Technology Consulting / Architecture / Lead / Solutions
        if any(k in t for k in ["consultant", "architect", "tech lead", "lead engineer", "solutions", "principal", "staff"]):
            return "consulting"

        # 4. Frontend / UI
        if any(k in t for k in ["frontend", "front end", "react", "next.js", "nextjs", "ui developer", "web developer"]):
            if "full stack" not in t and "fullstack" not in t:
                return "frontend"

        # 5. Full Stack
        if any(k in t for k in ["full stack", "fullstack", "end-to-end", "full-stack"]):
            return "fullstack"

        # 6. Backend / Python / API
        if any(k in t for k in ["backend", "back end", "python", "fastapi", "django", "flask", "api engineer", "database", "distributed"]):
            return "backend"

        # Check description signals if title was generic (e.g. "Software Engineer")
        if any(k in desc for k in ["fastapi", "django", "sqlalchemy", "celery", "postgres"]):
            return "backend"
        if any(k in desc for k in ["next.js", "react", "tailwind", "typescript"]):
            return "fullstack"
        if any(k in desc for k in ["flutter", "dart", "mobile app"]):
            return "mobile"

        return "base"

    def get_variant_latex(self, variant: str) -> str:
        """
        Injects the selected variant into the LaTeX template.
        """
        v = variant.strip().lower()
        if v not in VARIANTS_METADATA:
            v = "base"

        # Check if pre-generated variant file exists
        variant_file = settings.DATA_DIR / "resumes" / f"resume_{v}.tex"
        if variant_file.exists():
            try:
                return variant_file.read_text(encoding="utf-8")
            except Exception:
                pass

        # Otherwise replace variant definition in master template
        master = self._read_master_template()
        if not master:
            return ""

        import re
        replaced = re.sub(r"\\def\\Variant\{[a-zA-Z0-9_]+\}", f"\\\\def\\\\Variant{{{v}}}", master)
        return replaced

    def generate_variant_document(
        self,
        variant: str,
        company: str,
        job_title: str,
        job_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generates and compiles the resume variant into LaTeX and PDF.
        """
        tex_content = self.get_variant_latex(variant)
        comp_res = self.pdf_compiler.compile_resume(
            job_id=job_id or 0,
            company_slug=company,
            latex_content=tex_content,
            role_title=job_title or variant,
        )

        meta = VARIANTS_METADATA.get(variant, VARIANTS_METADATA["base"])
        return {
            "variant": variant,
            "headline": meta["headline"],
            "latex_content": tex_content,
            "pdf_path": comp_res.get("pdf_path", ""),
            "tex_path": comp_res.get("tex_path", ""),
            "success": comp_res.get("success", False),
        }
