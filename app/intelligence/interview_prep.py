"""
Interview Preparation Pack Generator.
Generates targeted technical and behavioral STAR interview prep packs tailored
to specific job postings and the candidate's authentic engineering background.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from app.intelligence.anti_slop import AntiSlopValidator
from app.intelligence.llm_client import UnifiedLLMClient

logger = logging.getLogger("personal_job_agent.intelligence.interview_prep")

CANDIDATE_EXPERIENCE_SUMMARY = (
    "Thigulla Meghraj Goud: Backend & Systems Engineer. "
    "Hands-on expertise across 286 API endpoints, 61 database models, and 30+ automated schema migrations. "
    "Core competencies: Python, FastAPI, AsyncIO, PostgreSQL, SQLAlchemy, Docker, Redis caching, "
    "data pipelines, sub-100ms API latency optimization, and 73.4% test coverage across 90 automated test suites."
)


class InterviewPrepGenerator:
    """
    Generates structured, realistic technical and behavioral interview preparation guides.
    """

    def __init__(self, llm_client: Optional[UnifiedLLMClient] = None):
        self.llm = llm_client or UnifiedLLMClient()
        self.validator = AntiSlopValidator()

    def generate_deterministic_pack(
        self,
        job_title: str,
        company: str,
        matched_skills: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Deterministic, authentic interview prep pack mapped to candidate's real profile.
        Used as primary fallback or offline mode.
        """
        skills = matched_skills or ["Python", "FastAPI", "PostgreSQL", "System Architecture"]
        primary_skill = skills[0] if skills else "Python"
        secondary_skill = skills[1] if len(skills) > 1 else "FastAPI"

        tech_questions = [
            {
                "question": f"How do you optimize asynchronous throughput and database connection pooling in {secondary_skill} / {primary_skill} under high concurrency?",
                "focus_area": "Concurrency & Database Performance",
                "talking_points": [
                    "Explain SQLAlchemy async engine configuration and NullPool / connection pool sizing based on Postgres worker capacity.",
                    "Discuss async event loop starvation prevention by offloading CPU-bound tasks to background threads or subprocesses.",
                    "Highlight indexing strategies (B-Tree, partial indexes) and query latency monitoring using EXPLAIN ANALYZE."
                ]
            },
            {
                "question": "Walk us through how you handle schema evolution and backward-compatible data migrations in production.",
                "focus_area": "Data Integrity & Schema Migrations",
                "talking_points": [
                    "Describe multi-step migrations: add nullable column -> backfill in batches -> make non-nullable -> drop old columns.",
                    "Reference managing 30+ Alembic and Prisma migrations without downtime or locked tables.",
                    "Discuss idempotency, atomic rollback mechanisms, and schema validation via automated test fixtures."
                ]
            },
            {
                "question": "How do you design defensive API boundaries and validate untrusted external inputs?",
                "focus_area": "API Architecture & Security",
                "talking_points": [
                    "Strict Pydantic payload validation and type coercion at the router boundary.",
                    "Rate limiting, brute-force protection, signed cryptographic session cookies, and constant-time HMAC validation.",
                    "Sanitizing scraped or third-party content against hidden payloads and injection attempts before persistence."
                ]
            }
        ]

        behavioral_questions = [
            {
                "question": "Tell me about a time you diagnosed and resolved a critical production bottleneck or outage.",
                "situation": "A production service experienced memory bloat and connection exhaustion during scheduled background jobs.",
                "task": "Identify root cause without taking down dependent API endpoints or breaching memory quotas.",
                "action": "Profiled process VmRSS, isolated memory-heavy libraries (like pandas/jobspy) into short-lived subprocesses, and tuned DB connection pool size from 10 to 2.",
                "result": "Memory consumption stabilized permanently below free-tier limits with zero 500 errors and sub-100ms response times."
            },
            {
                "question": "Describe a scenario where you had to prioritize architectural rigor versus shipping quickly.",
                "situation": "Rapidly implementing multi-board scrapers while preserving clean system boundaries and preventing regressions.",
                "task": "Deliver high coverage across new data sources while ensuring the test suite remains rock-solid.",
                "action": "Enforced strict test-driven development with isolated SQLite in-memory databases and mocked HTTP clients for 100+ tests.",
                "result": "Shipped new integrations on schedule with 100% CI pass rate and zero production regressions."
            },
            {
                "question": "How do you handle technical disagreements or ambiguous specifications within an engineering team?",
                "situation": "Ambiguity around caching strategy and data staleness vs database query load.",
                "task": "Align on an architecture that balances fresh data requirements with infrastructure cost.",
                "action": "Quantified actual query volume, tested a fingerprinting hash table with TTL, and shared measurable benchmarks with team members.",
                "result": "Replaced repetitive queries with 95% cache hit rates, avoiding expensive infrastructure upgrades."
            }
        ]

        questions_to_ask = [
            f"What does the engineering cadence and deployment cycle look like for the {job_title} team at {company}?",
            "What is the biggest technical bottleneck or architectural challenge the engineering team has tackled over the past two quarters?",
            "How does the engineering organization evaluate success and measure code quality for this role over the first 90 days?"
        ]

        markdown = self._format_markdown(
            job_title=job_title,
            company=company,
            tech_questions=tech_questions,
            behavioral_questions=behavioral_questions,
            questions_to_ask=questions_to_ask
        )

        return {
            "job_title": job_title,
            "company": company,
            "technical_questions": tech_questions,
            "behavioral_questions": behavioral_questions,
            "questions_to_ask": questions_to_ask,
            "markdown": markdown,
        }

    def _format_markdown(
        self,
        job_title: str,
        company: str,
        tech_questions: List[Dict[str, Any]],
        behavioral_questions: List[Dict[str, Any]],
        questions_to_ask: List[str],
    ) -> str:
        lines = [
            f"# 🎯 Interview Preparation Pack: {job_title} at {company}",
            "",
            "## 🛠️ 1. Technical & Architecture Questions",
            ""
        ]

        for i, q in enumerate(tech_questions, start=1):
            lines.append(f"### Q{i}: {q.get('question', '')}")
            lines.append(f"**Focus Area**: {q.get('focus_area', 'System Design')}")
            lines.append("**Key Talking Points**:")
            for pt in q.get("talking_points", []):
                lines.append(f"- {pt}")
            lines.append("")

        lines.extend([
            "## 🗣️ 2. Behavioral Questions (STAR Framework)",
            ""
        ])

        for i, b in enumerate(behavioral_questions, start=1):
            lines.append(f"### Q{i}: {b.get('question', '')}")
            lines.append(f"- **Situation**: {b.get('situation', '')}")
            lines.append(f"- **Task**: {b.get('task', '')}")
            lines.append(f"- **Action**: {b.get('action', '')}")
            lines.append(f"- **Result**: {b.get('result', '')}")
            lines.append("")

        lines.extend([
            "## ❓ 3. Strategic Questions to Ask Interviewers",
            ""
        ])

        for i, qa in enumerate(questions_to_ask, start=1):
            lines.append(f"{i}. {qa}")

        lines.append("")
        return "\n".join(lines)

    async def generate(
        self,
        job_title: str,
        company: str,
        description: str = "",
        matched_skills: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generates tailored interview prep using LLM if available, falling back to deterministic pack.
        """
        fallback = self.generate_deterministic_pack(job_title, company, matched_skills)

        prompt = (
            f"Generate a customized, professional interview preparation pack for {job_title} at {company}.\n\n"
            f"Candidate Profile: {CANDIDATE_EXPERIENCE_SUMMARY}\n"
            f"Relevant Skills: {', '.join(matched_skills or ['Python', 'FastAPI'])}\n"
            f"Job Description (excerpt): {description[:1200]}\n\n"
            "Return valid JSON matching this exact structure:\n"
            "{\n"
            '  "technical_questions": [\n'
            '    {"question": "...", "focus_area": "...", "talking_points": ["...", "..."]}\n'
            "  ],\n"
            '  "behavioral_questions": [\n'
            '    {"question": "...", "situation": "...", "task": "...", "action": "...", "result": "..."}\n'
            "  ],\n"
            '  "questions_to_ask": ["...", "..."]\n'
            "}\n\n"
            "Rules:\n"
            "1. Must be technically specific, grounded in realistic software engineering.\n"
            "2. Ground behavioral answers in candidate's backend, API, and database performance experience.\n"
            "3. ZERO buzzwords or AI slop.\n"
        )

        try:
            llm_res = await self.llm.generate(
                prompt=prompt,
                system_prompt="You are a principal engineer preparing a candidate for a technical interview. Output valid JSON only.",
                temperature=0.3,
                max_tokens=900,
            )
            raw_text = (llm_res.get("text") or "").strip()
            # Clean possible markdown fence
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:].strip()

            parsed = json.loads(raw_text)
            if (
                "technical_questions" in parsed
                and "behavioral_questions" in parsed
                and "questions_to_ask" in parsed
            ):
                tech_q = parsed["technical_questions"]
                beh_q = parsed["behavioral_questions"]
                q_ask = parsed["questions_to_ask"]
                markdown = self._format_markdown(
                    job_title=job_title,
                    company=company,
                    tech_questions=tech_q,
                    behavioral_questions=beh_q,
                    questions_to_ask=q_ask,
                )
                return {
                    "job_title": job_title,
                    "company": company,
                    "technical_questions": tech_q,
                    "behavioral_questions": beh_q,
                    "questions_to_ask": q_ask,
                    "markdown": markdown,
                }
            return fallback
        except Exception as e:
            logger.debug(f"LLM interview prep generation failed ({e}), using deterministic pack.")
            return fallback
