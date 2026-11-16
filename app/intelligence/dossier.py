"""
Company Executive Dossier & Strategic Intelligence Generator.
Inspired by AienTech/dossier and K-Sricharan/AI-LinkedIN-Jobs-Agent.
Synthesizes deep company intelligence, architectural stack deep-dives,
interviewer personas, tactical reverse-interview questions, and LinkedIn outreach assets.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from app.intelligence.company_research import KNOWN_COMPANIES, CompanyResearcher
from app.intelligence.llm_client import UnifiedLLMClient

logger = logging.getLogger("personal_job_agent.intelligence.dossier")


class CompanyDossierGenerator:
    """
    Compiles comprehensive company dossiers and recruiter outreach packs.
    """

    def __init__(self, llm_client: Optional[UnifiedLLMClient] = None):
        self.llm = llm_client or UnifiedLLMClient()
        self.researcher = CompanyResearcher()

    def _infer_tech_stack(self, text: str, matched_skills: List[str]) -> Dict[str, List[str]]:
        """Infers the probable production architecture from job description signals."""
        t = text.lower()
        backend = []
        for s in ["Python", "FastAPI", "Django", "Go", "Golang", "Node.js", "TypeScript", "C#", ".NET", "Java"]:
            if s.lower() in t or any(s.lower() == ms.lower() for ms in matched_skills):
                backend.append(s)
        if not backend:
            backend = ["Python", "FastAPI"]

        database = []
        for d in ["PostgreSQL", "Postgres", "Redis", "MySQL", "MongoDB", "DynamoDB", "ClickHouse", "Elasticsearch"]:
            if d.lower() in t:
                database.append(d)
        if not database:
            database = ["PostgreSQL", "Redis"]

        infra = []
        for i in ["AWS", "GCP", "Kubernetes", "Docker", "Terraform", "Serverless", "Azure"]:
            if i.lower() in t:
                infra.append(i)
        if not infra:
            infra = ["AWS", "Docker"]

        return {
            "backend": list(dict.fromkeys(backend))[:4],
            "database": list(dict.fromkeys(database))[:3],
            "infrastructure": list(dict.fromkeys(infra))[:3],
        }

    def generate_dossier(
        self,
        company: str,
        job_title: str,
        job_url: str = "",
        description: str = "",
        matched_skills: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Compiles an in-depth intelligence dossier for candidate interview preparation.
        """
        matched_skills = matched_skills or ["Python", "FastAPI", "PostgreSQL", "System Design"]
        base_research = self.researcher.research_company(
            company=company,
            job_title=job_title,
            job_url=job_url,
            description=description,
        )

        domain = base_research.get("domain", f"{re.sub(r'[^a-zA-Z0-9]', '', company.lower())}.com")
        archetype = base_research.get("archetype", "High-Growth Software Platform")
        scale = base_research.get("scale_estimate", "100-500 employees")
        tech_stack = self._infer_tech_stack(description, matched_skills)

        # Check if company is in curated registry
        comp_key = company.strip().lower()
        curated_match = None
        for k, v in KNOWN_COMPANIES.items():
            if k in comp_key or comp_key in k:
                curated_match = v
                break

        if curated_match:
            scale_challenges = [
                f"Peak Volume & Concurrency: Maintaining SLA under heavy market activity ({curated_match.get('primary_engineering_focus')}).",
                "Service Boundaries: Preventing cascading failures across microservices through resilient circuit breakers and event-driven architectures.",
                "Zero-Downtime Data Evolution: Schema migrations without lock contention on production transactional databases."
            ]
        else:
            scale_challenges = [
                f"High-Throughput Ingestion: Scaling API gateways and background async workers as {archetype.lower()} transaction volume doubles.",
                "Data Isolation & Multi-Tenancy: Ensuring strict tenant separation and data integrity with sub-millisecond query performance.",
                "System Observability: Achieving distributed tracing across services to detect latency regressions before users are impacted."
            ]

        # Strategic Reverse Interview Questions
        reverse_questions = [
            f"Given your current focus on {tech_stack['backend'][0] if tech_stack['backend'] else 'Python'}, what has been your team's biggest technical bottleneck as service volume expanded?",
            f"How does the engineering organization balance building new {archetype} product features against paying down architectural tech debt?",
            "What does the deployment and rollback cadence look like when pushing backend schema updates to high-traffic database clusters?",
            "For this specific role, what would a successful 90-day outcome look like in terms of system reliability or platform ownership?"
        ]

        # LinkedIn Outreach Assets (Inspired by AI-LinkedIN-Jobs-Agent)
        clean_company = company.strip()
        first_skill = matched_skills[0] if matched_skills else "Python"
        second_skill = matched_skills[1] if len(matched_skills) > 1 else "FastAPI"

        linkedin_connect_note = (
            f"Hi! Noticed the {job_title} opening at {clean_company}. I'm a Backend Engineer "
            f"specializing in {first_skill} & {second_skill} (built systems serving 100k+ req/day). "
            f"Would love to connect and follow your engineering updates!"
        )[:295]

        linkedin_inmail = (
            f"Subject: {job_title} application — Thigulla Meghraj Goud\n\n"
            f"Hi Hiring Team,\n\n"
            f"I recently applied for the {job_title} position at {clean_company}. "
            f"With 2+ years building high-throughput backend services in {first_skill}, {second_skill}, "
            f"and PostgreSQL, I've engineered systems reducing API latency by 35% and automating 280+ API contracts.\n\n"
            f"I would appreciate a brief conversation regarding how my background in distributed systems "
            f"can accelerate {clean_company}'s engineering objectives.\n\n"
            f"Best regards,\nThigulla Meghraj Goud\nmeghraj.thigulla@outlook.com"
        )

        return {
            "company": clean_company,
            "job_title": job_title,
            "domain": domain,
            "archetype": archetype,
            "scale_estimate": scale,
            "tech_stack": tech_stack,
            "engineering_focus": base_research.get("primary_engineering_focus", ""),
            "scale_challenges": scale_challenges,
            "interviewer_persona": {
                "archetype": "Pragmatic Systems Architect",
                "core_priorities": [
                    "Production reliability and clean API boundaries over hype-driven complexity.",
                    "Demonstrated ownership of production incidents and deep SQL tuning experience.",
                    "Clarity in trade-offs (e.g. latency vs consistency, async workers vs synchronous calls)."
                ],
                "anti_patterns": [
                    "Buzzword soup without metric-backed verification.",
                    "Proposing complex microservices where a clean modular monolith is optimal."
                ]
            },
            "reverse_interview_questions": reverse_questions,
            "linkedin_outreach": {
                "connection_request_note": linkedin_connect_note,
                "recruiter_inmail": linkedin_inmail,
                "char_count_note": len(linkedin_connect_note),
            },
            "is_curated": bool(curated_match)
        }
