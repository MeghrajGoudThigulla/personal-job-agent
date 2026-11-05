import json
from pathlib import Path
from typing import Dict, Any
from app.config import settings
from app.intelligence.anti_slop import AntiSlopValidator

class OutreachGenerator:
    """
    Generates personalized cold emails and LinkedIn sequences following
    the MPM JobHunt Cheat Sheet guidelines while adhering to Anti-Slop principles.
    """

    def __init__(self, templates_path: Path = None):
        self.templates_path = templates_path or settings.COLD_TEMPLATES_JSON
        self.anti_slop = AntiSlopValidator()
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict[str, Any]:
        if self.templates_path and self.templates_path.exists():
            try:
                with open(self.templates_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def generate_outreach(
        self,
        job_title: str,
        company: str,
        job_url: str,
        matched_skills: list,
        recruiter_name: str = "Hiring Team",
        manager_name: str = "Engineering Lead"
    ) -> Dict[str, Any]:
        """
        Creates personalized email drafts and LinkedIn 4MM sequence.
        """
        s1 = matched_skills[0].title() if len(matched_skills) > 0 else "Python"
        s2 = matched_skills[1].title() if len(matched_skills) > 1 else "FastAPI"
        s3 = matched_skills[2].title() if len(matched_skills) > 2 else "PostgreSQL"

        # 1. HR / Recruiter Email (No bold text in final output)
        hr_subject = f"Keen to contribute to {company} as a {job_title}"
        hr_body = (
            f"Hello {recruiter_name},\n\n"
            f"I came across the job opportunity for {job_title} ({job_url}) with your engineering team at {company}.\n\n"
            f"My core background is in {s1}, {s2}, and {s3}, which directly aligns with the technical demands of the role. "
            f"In my recent work, I delivered backend infrastructure comprising 286 endpoints, 61+ database models, and 30+ Alembic/Prisma migrations across production services, "
            f"owning schema architecture and concurrency control end-to-end.\n\n"
            f"I do not approach engineering as a checkbox task—I focus on high reliability, clear API boundaries, and low operational overhead. "
            f"I would welcome the opportunity to connect for a quick 15-minute chat to discuss how my background can directly assist your engineering roadmap.\n\n"
            f"Best regards,\n"
            f"Thigulla Meghraj Goud\n"
            f"LinkedIn: https://www.linkedin.com/in/meghraj-goud-thigulla\n"
            f"Portfolio: https://meghraj-portfolio.web.app/\n"
            f"Phone: +91 79972 21772"
        )

        # 2. Hiring Manager / Engineering Peer Email
        hm_subject = f"Question regarding {company}'s {s1} & {s2} architecture"
        hm_body = (
            f"Hello {manager_name},\n\n"
            f"I've been closely following {company}'s engineering work and notice your team is actively scaling systems around {job_title}.\n\n"
            f"My experience centers on high-throughput backend services ({s1}, {s2}, {s3}), transactional reliability (Transactional Outbox Pattern, optimistic concurrency), "
            f"and ML inference pipeline deployment. For example, in my open-source applicant tracking pipeline TalentFlow, I maintained 73.4% test coverage across 90 automated tests.\n\n"
            f"I'd love to hear your perspective on what separates good engineers from great ones on your team. Would you be open to a 10-minute sync this week?\n\n"
            f"Regards,\n"
            f"Thigulla Meghraj Goud\n"
            f"meghraj.thigulla@outlook.com | +91 79972 21772\n"
            f"https://github.com/MeghrajGoudThigulla"
        )

        # 3. LinkedIn 4MM Sequence
        l1 = f"Hello {manager_name}, saw your engineering leadership at {company}. My background in {s1} and {s2} aligns closely with your team's stack. Would love to connect!"
        l2 = f"Thanks for connecting, {manager_name}! If you have 60 seconds, I'd value your candid glance at my resume (https://meghraj-portfolio.web.app/) on how it aligns with {company}'s engineering standards."
        l3 = f"Appreciate the feedback, {manager_name}. I refined my profile to emphasize {s1} system design and production reliability. Hope this resonates with what {company} builds."
        l4 = f"Hi {manager_name}, I saw the open {job_title} opening at {company} ({job_url}). It is an exact fit with my production background. Would you be open to referring me internally?"

        # Sanitize all for anti-slop
        hr_body = self.anti_slop.sanitize_text(hr_body)
        hm_body = self.anti_slop.sanitize_text(hm_body)

        return {
            "hr_email": {
                "subject": hr_subject,
                "body": hr_body
            },
            "hiring_manager_email": {
                "subject": hm_subject,
                "body": hm_body
            },
            "linkedin_4mm": {
                "m1_connect": l1,
                "m2_feedback": l2,
                "m3_alignment": l3,
                "m4_referral": l4
            }
        }
