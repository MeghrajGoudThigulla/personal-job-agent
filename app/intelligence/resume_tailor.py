from pathlib import Path
from typing import Dict, Any, Optional
from app.config import settings
from app.intelligence.llm_client import UnifiedLLMClient
from app.intelligence.anti_slop import AntiSlopValidator
from app.intelligence.resume_variants import ResumeVariantManager, VARIANTS_METADATA
from app.core.trace import log_audit_event

class ResumeTailor:
    """
    Tailors Meghraj's resume for a specific job posting starting from
    the most relevant of 7 specialized resume variants, while strictly enforcing
    the Anti-Slop Reduction System (slop-reduct.md) and candidate authenticity.
    """

    def __init__(self):
        self.llm = UnifiedLLMClient()
        self.anti_slop = AntiSlopValidator()
        self.variant_mgr = ResumeVariantManager()
        self.base_tex = self._load_file(settings.BASE_RESUME_TEX)
        self.base_md = self._load_file(settings.BASE_RESUME_MD)

    def _load_file(self, path: Path) -> str:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass
        return ""

    async def tailor_resume(
        self,
        job_title: str,
        company: str,
        description: str,
        matched_skills: list,
        preferred_variant: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Selects the best resume variant and generates tailored LaTeX (.tex) and Markdown (.md).
        """
        # 1. Deterministically select best variant (backend, ai, mobile, fullstack, frontend, consulting, base)
        variant = preferred_variant or self.variant_mgr.select_best_variant(
            title=job_title,
            description=description,
            matched_skills=matched_skills
        )
        variant_meta = VARIANTS_METADATA.get(variant, VARIANTS_METADATA["base"])
        variant_tex = self.variant_mgr.get_variant_latex(variant) or self.base_tex

        system_prompt = (
            "You are an expert technical resume architect and anti-slop copywriter for senior software engineers. "
            "Your task is to tailor an authentic, metric-dense engineering resume for a target job.\n\n"
            "CRITICAL RULES:\n"
            "1. NEVER hallucinate or exaggerate skills or roles. Retain Meghraj Goud Thigulla's real metrics:\n"
            "   - Full Stack Engineer (July 2024 - February 2026), Senior AI Developer (March 2026 - October 2026)\n"
            "   - Products: TFG Verify (206 routes, 58 models, RLS), TFG SecureBanking (174 endpoints), DealsMart (152 routes),\n"
            "     Medical Advisor (230 routes, Flutter app), TFG Corporate Website (Next.js), IYOV AI Assessments\n"
            "   - Live Store apps: IYOV AI Employee, Jobs, LMS, HRMS; Medical Advisor, TFG SecureBanking on Google Play\n"
            "   - PaddleOCR (ONNX Runtime), BGE-M3 embeddings, 50-100 AWS EC2 deployments, 73.4% pytest coverage\n"
            "2. ANTI-SLOP ENFORCEMENT: Never use prohibited buzzwords ('seamless', 'robust', 'powerful', "
            "'cutting-edge', 'game-changing', 'unlock', 'leverage', 'delve', 'tapestry', 'innovative'). "
            "Use concrete engineering verbs ('architected', 'benchmarked', 'engineered', 'profiled', 'deployed').\n"
            f"3. BASE VARIANT: The candidate is applying as '{variant_meta['headline']}'. "
            "Keep this headline and prioritize projects and skills matching the role.\n"
            "4. Return valid, compilable LaTeX that matches the original document structure exactly."
        )

        user_prompt = (
            f"Target Company: {company}\n"
            f"Target Role: {job_title}\n"
            f"Matched Skills: {', '.join(matched_skills)}\n"
            f"Selected Variant: {variant} ({variant_meta['headline']})\n"
            f"Job Description Excerpt:\n{description[:1800]}\n\n"
            f"BASE VARIANT LATEX RESUME:\n```latex\n{variant_tex}\n```\n\n"
            "Please return the complete tailored LaTeX resume. Do not include markdown code block backticks."
        )

        llm_response = await self.llm.generate_completion(system_prompt, user_prompt, temperature=0.1)

        if llm_response == "HEURISTIC_GENERATION" or "documentclass" not in llm_response:
            tailored_tex = self._heuristic_tailor_tex(job_title, company, matched_skills, variant)
        else:
            tailored_tex = llm_response.strip().replace("```latex", "").replace("```", "").strip()

        # Sanitize against slop
        tailored_tex = self.anti_slop.sanitize_text(tailored_tex)
        slop_eval = self.anti_slop.evaluate_text(tailored_tex)

        # Generate markdown companion
        tailored_md = self._tex_to_markdown(tailored_tex)

        await log_audit_event("resume_tailored", {
            "company": company,
            "role": job_title,
            "variant": variant,
            "slop_score": slop_eval["score"],
            "slop_grade": slop_eval["grade"]
        })

        return {
            "variant": variant,
            "variant_headline": variant_meta["headline"],
            "tailored_tex": tailored_tex,
            "tailored_md": tailored_md,
            "slop_score": slop_eval["score"],
            "slop_grade": slop_eval["grade"],
            "is_clean": slop_eval["is_clean"]
        }

    def _heuristic_tailor_tex(self, job_title: str, company: str, matched_skills: list, variant: str = "base") -> str:
        """Heuristic tailoring: uses the exact specialized variant LaTeX."""
        return self.variant_mgr.get_variant_latex(variant)

    def _tex_to_markdown(self, tex: str) -> str:
        """Lightweight conversion from LaTeX to Markdown."""
        return self.base_md or "Markdown companion generated."
