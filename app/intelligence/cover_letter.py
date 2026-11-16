"""
Text-Only Cover Letter Generator.
Produces high-converting, metric-dense, text-only cover letters (<220 words)
strictly adhering to the Anti-Slop Reduction System.
Formatted for direct copy-pasting and delivered alongside Telegram job alerts.
"""

from __future__ import annotations

import logging
from typing import List, Optional
from app.intelligence.anti_slop import AntiSlopValidator
from app.intelligence.llm_client import UnifiedLLMClient

logger = logging.getLogger("personal_job_agent.intelligence.cover_letter")

CANDIDATE_NAME = "Thigulla Meghraj Goud"
CANDIDATE_EMAIL = "meghraj.thigulla@outlook.com"
CANDIDATE_PHONE = "+91 79972 21772"
CANDIDATE_PORTFOLIO = "https://meghraj-portfolio.web.app/"
CANDIDATE_GITHUB = "https://github.com/MeghrajGoudThigulla"


class CoverLetterGenerator:
    """
    Generates tailored, text-only cover letters without AI fluff.
    """

    def __init__(self, llm_client: Optional[UnifiedLLMClient] = None):
        self.llm = llm_client or UnifiedLLMClient()
        self.validator = AntiSlopValidator()

    def generate_fallback_text(
        self,
        job_title: str,
        company: str,
        matched_skills: Optional[List[str]] = None,
    ) -> str:
        """
        Deterministic, anti-slop verified text template.
        Guaranteed to stay under 200 words and 0 slop score.
        """
        skills = matched_skills or ["Python", "FastAPI", "PostgreSQL", "System Architecture"]
        s1 = skills[0] if len(skills) > 0 else "Python"
        s2 = skills[1] if len(skills) > 1 else "FastAPI"
        s3 = skills[2] if len(skills) > 2 else "PostgreSQL"

        text = (
            f"Dear {company} Hiring Team,\n\n"
            f"I am writing to express my focused interest in the {job_title} role at {company}. "
            f"My engineering background centers on backend service architecture, high-concurrency data pipelines, "
            f"and production reliability with {s1}, {s2}, and {s3}.\n\n"
            f"In my recent work, I built and maintained backend infrastructure spanning 286 API endpoints, "
            f"61 database models, and 30+ automated schema migrations, ensuring transactional consistency and sub-100ms response times. "
            f"I also developed automated evaluation and data ingestion pipelines maintaining 73.4% test coverage across 90 automated test suites.\n\n"
            f"I focus on clean API boundaries, pragmatic architecture, and shipping maintainable code without operational overhead. "
            f"I would welcome the opportunity to discuss how my hands-on background with {s1} and {s2} aligns with your engineering goals.\n\n"
            f"Sincerely,\n"
            f"{CANDIDATE_NAME}\n"
            f"{CANDIDATE_EMAIL} | {CANDIDATE_PHONE}\n"
            f"Portfolio: {CANDIDATE_PORTFOLIO} | GitHub: {CANDIDATE_GITHUB}"
        )
        return text

    async def generate(
        self,
        job_title: str,
        company: str,
        description: str = "",
        matched_skills: Optional[List[str]] = None,
    ) -> str:
        """
        Generates a concise, authentic text-only cover letter (<220 words).
        Attempts LLM generation with anti-slop rules; falls back to deterministic template on error.
        """
        fallback = self.generate_fallback_text(job_title, company, matched_skills)

        prompt = (
            f"Write a concise, high-impact, text-only cover letter (<200 words) for {CANDIDATE_NAME} "
            f"applying for '{job_title}' at '{company}'.\n\n"
            f"Target Requirements & Skills: {', '.join(matched_skills or ['Python', 'FastAPI'])}\n"
            f"Job Description excerpt: {description[:1200]}\n\n"
            f"CANDIDATE FACTS (DO NOT EXAGGERATE OR INVENT):\n"
            f"- 286 endpoints, 61+ database models, 30+ Alembic/Prisma migrations across production services\n"
            f"- High-concurrency async pipelines, FastAPI, PostgreSQL, Docker, Flutter, React\n"
            f"- Open source ATS (TalentFlow): 73.4% test coverage across 90 automated tests\n"
            f"- Contact: {CANDIDATE_EMAIL} | {CANDIDATE_PHONE} | {CANDIDATE_PORTFOLIO}\n\n"
            f"CRITICAL ANTI-SLOP RULES:\n"
            f"1. Maximum 200 words total.\n"
            f"2. ZERO buzzwords: absolutely no 'delve', 'tapestry', 'robust', 'seamless', 'cutting-edge', 'thrilled', 'passionate'.\n"
            f"3. Pure plain text only with standard paragraph breaks. No markdown headers, no bold asterisks.\n"
            f"4. Salutation: 'Dear {company} Hiring Team,'\n"
            f"5. End with candidate name, email, phone, and links.\n"
        )

        try:
            llm_res = await self.llm.generate(
                prompt=prompt,
                system_prompt="You are an anti-slop engineering career agent. Output raw plain text cover letters only.",
                temperature=0.3,
                max_tokens=400,
            )
            raw_text = (llm_res.get("text") or "").strip()
            # Remove any markdown formatting (e.g. bolding)
            raw_text = raw_text.replace("**", "").replace("##", "").strip()

            eval_res = self.validator.evaluate_text(raw_text)
            if eval_res["is_clean"] and 50 <= eval_res["word_count"] <= 260:
                return raw_text
            elif eval_res["word_count"] >= 50:
                sanitized = self.validator.sanitize_text(raw_text)
                return sanitized
            else:
                return fallback
        except Exception as e:
            logger.debug(f"LLM cover letter generation failed ({e}), using deterministic template.")
            return fallback
