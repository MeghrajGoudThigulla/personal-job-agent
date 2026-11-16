"""
Daily LinkedIn Post Generator & Engineering Voice Engine.
Generates authentic, metric-dense, anti-slop LinkedIn posts reflecting
Thigulla Meghraj Goud's real engineering experiences and technical architecture decisions.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import logging
from typing import Any, Dict, List, Optional
from app.intelligence.llm_client import UnifiedLLMClient
from app.intelligence.anti_slop import AntiSlopValidator
from app.core.trace import log_audit_event

logger = logging.getLogger("personal_job_agent.intelligence.linkedin_post")

IST = timezone(timedelta(hours=5, minutes=30))

ENGINEERING_THEMES: List[Dict[str, Any]] = [
    {
        "theme": "Backend Architecture & Database Schema Evolution",
        "focus": "FastAPI, 206 routes, 58 SQLAlchemy models, Row-Level Security, 25 Alembic migrations without downtime.",
        "key_metric": "206 REST API endpoints and zero-downtime migrations on live production PostgreSQL.",
        "sample_hook": "Most teams overcomplicate microservices before they even need them. Here is how we scaled a single FastAPI service to 206 endpoints with zero lock contention.",
        "fallback_post": (
            "Most teams rush into microservices before their domain boundaries even settle.\n\n"
            "While building TFGenAPI, we kept our architecture lean: a single, modular FastAPI backend containing "
            "206 API routes, 58 SQLAlchemy models, and 25 Alembic migrations.\n\n"
            "Key architectural choices that kept the system fast and maintainable:\n"
            "1. Row-Level Security (RLS) directly inside PostgreSQL for multi-tenant isolation, eliminating custom application authorization leaks.\n"
            "2. Celery + Redis workers with signed webhooks to decouple long-running background verification steps from client request-response cycles.\n"
            "3. Strict zero-lock migration patterns on high-write production tables (adding nullable columns first, populating asynchronously, then adding constraints).\n\n"
            "A clean modular monolith with clear service boundaries will out-scale messy microservice spaghetti every single time.\n\n"
            "How does your team decide when to split a service?"
        ),
        "hashtags": "#softwareengineering #python #fastapi #systemdesign #backend #postgresql"
    },
    {
        "theme": "Edge AI & Production OCR Optimization",
        "focus": "PaddleOCR on ONNX Runtime, 64-type document taxonomy, BGE-M3 embeddings, 8 docs/min, 75% latency drop.",
        "key_metric": "75% reduction in manual verification overhead and 8 documents processed per minute.",
        "sample_hook": "You don't always need expensive proprietary LLM APIs for document extraction. Here is how we cut document processing latency by 75% using open weights.",
        "fallback_post": (
            "You don't always need to burn $0.03 per page calling proprietary vision models for document verification.\n\n"
            "When building our automated KYC pipeline, we chose an edge-optimized architecture:\n"
            "• Engine: PaddleOCR running on ONNX Runtime with quantized weights.\n"
            "• Classification: A 64-type document taxonomy paired with BGE-M3 local dense embeddings and RapidFuzz matching.\n"
            "• Throughput: ~8 documents processed per minute on standard EC2 instances.\n\n"
            "The outcome?\n"
            "A 75% reduction in manual human verification time, zero external API latency spikes, and predictable infrastructure costs that didn't spike with usage.\n\n"
            "Are you running document intelligence on the edge or relying entirely on hosted APIs?"
        ),
        "hashtags": "#machinelearning #appliedai #computervision #python #onnx #aiengineering"
    },
    {
        "theme": "Mobile Release Velocity & Store Operations",
        "focus": "Shipping 6 Flutter apps to Google Play and Apple App Store in under 1 hour per platform.",
        "key_metric": "6 release builds prepared and submitted under 60 minutes per platform.",
        "sample_hook": "Releasing mobile apps doesn't have to take an entire afternoon of manual cert signing and asset juggling.",
        "fallback_post": (
            "Releasing mobile apps shouldn't require an entire afternoon of manual signing keys, provisioning profile conflicts, and Xcode errors.\n\n"
            "Across our workforce suite (IYOV AI Employee, Jobs, LMS, HRMS, and Medical Advisor), we standardized our Flutter release pipeline:\n"
            "1. Parameterized Fastlane scripts handling version bumping, keystore injections, and Play Console / App Store Connect API uploads.\n"
            "2. Isolated build flavors separating staging APIs from production telemetry.\n"
            "3. Automated store artifact packaging under 1 hour across both platforms.\n\n"
            "When deployment is predictable and scriptable, your team stops fearing store submissions and starts shipping continuous bug fixes with confidence.\n\n"
            "What is the biggest bottleneck in your team's mobile release cycle?"
        ),
        "hashtags": "#flutter #mobiledevelopment #iosdev #androiddev #cicd #devops"
    },
    {
        "theme": "Statutory Business Logic & Financial Precision",
        "focus": "Building an India statutory payroll engine (PF, ESI, TDS, professional tax) with mathematical rigor.",
        "key_metric": "100% automated India statutory compliance calculations without spreadsheet dependencies.",
        "sample_hook": "Building payroll software in India is a masterclass in edge-case handling. Here is what we learned translating tax laws into Python code.",
        "fallback_post": (
            "Building statutory payroll logic in India is a masterclass in domain modeling and edge-case precision.\n\n"
            "When we built the automated payroll module for IYOV AI, we had to encode:\n"
            "• PF wage ceiling capping vs voluntary contributions.\n"
            "• ESI gross limits and state-specific Professional Tax slab structures.\n"
            "• Dual-regime TDS tax deductions and annual rebate projections.\n\n"
            "The golden rule: Never use standard floating-point arithmetic for monetary calculations. Always use Python's `decimal.Decimal` with explicit rounding modes (`ROUND_HALF_UP`), and encapsulate rule sets into pure, testable domain functions.\n\n"
            "The result was eliminating manual calculation steps for our internal payroll workflows and catching variance bugs before pay slips were generated.\n\n"
            "What is the most complex domain logic you've had to encode into software?"
        ),
        "hashtags": "#python #fintech #softwareengineering #cleancode #backend"
    },
    {
        "theme": "Testing Rigor & Pytest Code Coverage",
        "focus": "Raising pytest coverage from 43% to 73.4% without writing low-value mock tests.",
        "key_metric": "Coverage climbed from 43% to 73.4% across mission-critical services.",
        "sample_hook": "Unit test coverage is a vanity metric if you're only testing getters and setters. Here is how we genuinely hardened our test suite from 43% to 73.4%.",
        "fallback_post": (
            "Unit test coverage is a dangerous vanity metric if you're only writing tests to hit a percentage target.\n\n"
            "When we audited our backend test suite, coverage was at 43%, and regression bugs still slipped through. Here is how we reached 73.4% with meaningful tests:\n"
            "1. Integration tests with Testcontainers / transient PostgreSQL instead of over-mocked repositories.\n"
            "2. Testing error boundaries: validating that database rollbacks execute when external webhooks fail halfway through checkout.\n"
            "3. Contract testing on our 200+ REST endpoints to ensure response schemas never break frontend clients.\n\n"
            "Testing should give you the courage to refactor legacy code on a Friday afternoon without breaking production.\n\n"
            "What percentage of your test suite tests business logic vs infrastructure wiring?"
        ),
        "hashtags": "#pytest #python #testing #softwareengineering #backend #quality"
    },
    {
        "theme": "Cloud Infrastructure & Deployment Speed",
        "focus": "Deploying 50-100 applications to AWS EC2 with systemd, nginx, and zero-downtime rollback scripts.",
        "key_metric": "50-100 deployments completed typically in under 30 minutes each.",
        "sample_hook": "You don't always need a complex Kubernetes cluster to achieve rock-solid uptime and fast deploys.",
        "fallback_post": (
            "You don't always need a multi-node Kubernetes cluster to achieve rock-solid uptime and fast deployments.\n\n"
            "For many high-velocity engineering environments, a well-tuned systemd + nginx reverse proxy setup on AWS EC2 provides:\n"
            "• Sub-minute service restarts with graceful socket handoffs.\n"
            "• Predictable memory footprints without container overlay network overhead.\n"
            "• Automated rollback scripts that revert binaries and database schema pointers instantly if health checks fail.\n\n"
            "We executed between 50 to 100 EC2 rollouts and updates, typically completing each release in under 30 minutes with zero customer-facing downtime.\n\n"
            "Choose boring, reliable infrastructure until scale demands complexity.\n\n"
            "What is your team's default deployment target?"
        ),
        "hashtags": "#devops #aws #cloud #sysadmin #softwareengineering #infrastructure"
    },
    {
        "theme": "Technical Mentorship & Ambiguous Requirements",
        "focus": "Mentoring 8 engineers and turning ambiguous business goals into shippable milestones.",
        "key_metric": "Mentored 8 engineers through codebase walkthroughs and system architecture.",
        "sample_hook": "The biggest differentiator of a senior engineer isn't typing speed or memorizing algorithms—it's converting business ambiguity into deliverable architecture.",
        "fallback_post": (
            "The biggest differentiator of an effective senior engineer isn't raw syntax speed or LeetCode tricks.\n\n"
            "It is the ability to sit with a stakeholder who says 'we need a smarter loan approval workflow' and translate that into:\n"
            "• Concrete REST endpoint contracts.\n"
            "• Clear database schema invariants.\n"
            "• Defined retry policies and failure fallbacks.\n"
            "• Shippable, weekly sprint milestones that junior engineers can execute without ambiguity.\n\n"
            "Mentoring 8 engineers taught me that clear documentation and architectural walkthroughs save 10x more time than writing the code yourself.\n\n"
            "How does your team translate vague product requests into technical roadmaps?"
        ),
        "hashtags": "#leadership #mentorship #softwareengineering #career #techlead"
    }
]


class LinkedInPostGenerator:
    """Generates daily technical LinkedIn posts adhering to authentic engineering metrics."""

    def __init__(self, llm_client: Optional[UnifiedLLMClient] = None):
        self.llm = llm_client or UnifiedLLMClient()
        self.anti_slop = AntiSlopValidator()

    def get_todays_theme(self, target_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Picks a rotating theme based on day of year for deterministic variety."""
        dt = target_date or datetime.now(IST)
        idx = dt.timetuple().tm_yday % len(ENGINEERING_THEMES)
        return ENGINEERING_THEMES[idx]

    async def generate_daily_post(
        self,
        topic_override: Optional[str] = None,
        theme_override: Optional[str] = None,
        target_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Drafts a high-impact, authentic technical post for LinkedIn.
        """
        dt = target_date or datetime.now(IST)
        date_str = dt.strftime("%Y-%m-%d")

        theme_data = None
        if theme_override:
            for t in ENGINEERING_THEMES:
                if theme_override.lower() in t["theme"].lower():
                    theme_data = t
                    break
        if not theme_data:
            theme_data = self.get_todays_theme(dt)

        system_prompt = (
            "You are a technical ghostwriter and senior engineering mentor for Meghraj Goud Thigulla, "
            "a Senior AI Developer & Full Stack Engineer specializing in Python, FastAPI, Flutter, PostgreSQL, and Applied AI.\n\n"
            "VOICE & STYLE GUIDELINES:\n"
            "1. AUTHENTIC & METRIC-BACKED: Speak with quiet confidence from real production experience. "
            "Use real numbers (206 endpoints, 58 models, 25 Alembic migrations, PaddleOCR on ONNX, 8 docs/min, 73.4% test coverage, AWS EC2, Flutter Riverpod).\n"
            "2. ANTI-SLOP ENFORCEMENT: Strictly prohibit AI clichés and buzzword slop:\n"
            "   - NO: 'I am thrilled to announce', 'In today's fast-paced digital world', 'game-changing', 'delve', 'tapestry', 'testament', 'revolutionize'.\n"
            "   - YES: Clear architectural trade-offs, code decisions, latency numbers, and operational realities.\n"
            "3. FORMATTING FOR LINKEDIN:\n"
            "   - Strong 1-2 line hook stopping the scroll.\n"
            "   - Short, punchy paragraphs (1-3 sentences max) with clean bullet points.\n"
            "   - A practical engineering takeaway or contrarian lesson.\n"
            "   - Engaging closing question to prompt thoughtful engineering comments.\n"
            "   - 4-5 relevant hashtags at the end."
        )

        user_prompt = (
            f"Topic: {topic_override or theme_data['theme']}\n"
            f"Context / Metrics: {theme_data['focus']}\n"
            f"Key Metric: {theme_data['key_metric']}\n\n"
            "Please write a complete, ready-to-publish LinkedIn post."
        )

        llm_response = await self.llm.generate_completion(system_prompt, user_prompt, temperature=0.3)

        if not llm_response or llm_response == "HEURISTIC_GENERATION" or len(llm_response.strip()) < 100:
            post_content = theme_data["fallback_post"]
            hook = theme_data["sample_hook"]
            hashtags = theme_data["hashtags"]
        else:
            post_content = self.anti_slop.sanitize_text(llm_response.strip())
            # Extract first line as hook
            lines = [line.strip() for line in post_content.splitlines() if line.strip()]
            hook = lines[0] if lines else theme_data["sample_hook"]
            hashtags = theme_data["hashtags"]
            if "#" in post_content:
                # If LLM included hashtags, keep them
                pass

        slop_eval = self.anti_slop.evaluate_text(post_content)

        await log_audit_event("linkedin_post_generated", {
            "date": date_str,
            "theme": theme_data["theme"],
            "slop_score": slop_eval["score"],
            "slop_grade": slop_eval["grade"]
        })

        return {
            "date": date_str,
            "theme": theme_data["theme"],
            "hook": hook,
            "content": post_content,
            "hashtags": hashtags,
            "call_to_action": "Share your thoughts or engineering trade-offs in the comments.",
            "slop_score": slop_eval["score"],
            "slop_grade": slop_eval["grade"],
            "is_clean": slop_eval["is_clean"],
        }

