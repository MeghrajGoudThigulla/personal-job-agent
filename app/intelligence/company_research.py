"""
Company Research and Public Domain Signal Intelligence Module.
Extracts company domain signals, architectural focus areas, engineering archetypes,
and targeted technical interview angles based on job context and company metadata.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse

# Curated knowledge base for prominent technology employers and scaleups
KNOWN_COMPANIES: Dict[str, Dict[str, Any]] = {
    "zerodha": {
        "domain": "zerodha.com",
        "archetype": "Bootstrapped Fintech Leader",
        "scale_estimate": "1,000-2,000 employees",
        "primary_engineering_focus": "Ultra-low latency order routing, clean architecture, minimal dependencies, open-source stack (Python, Go, PostgreSQL).",
        "interview_angles": [
            "Pragmatic simplicity: avoiding Kubernetes/microservice bloat when vertical scaling and Postgres tuning suffice.",
            "Atomic transaction processing and sub-10ms trade execution under peak Indian market opening volume.",
            "Reliability without vendor lock-in: bare metal infrastructure and open-source systems."
        ]
    },
    "razorpay": {
        "domain": "razorpay.com",
        "archetype": "Fintech Infrastructure & Payments",
        "scale_estimate": "3,000-5,000 employees (Scaleup / Pre-IPO)",
        "primary_engineering_focus": "High-availability payment gateways, idempotent webhooks, distributed settlement ledgers, and zero-downtime deployments.",
        "interview_angles": [
            "Idempotency patterns and two-phase commits across external banking switches and UPI rails.",
            "Handling flash sales with 10,000+ payment requests per second with circuit breakers.",
            "Multi-tenant database schema isolation and PCI-DSS compliance."
        ]
    },
    "swiggy": {
        "domain": "swiggy.com",
        "archetype": "Hyper-Growth On-Demand Logistics",
        "scale_estimate": "5,000+ employees (Public)",
        "primary_engineering_focus": "Real-time dispatching algorithms, geospatial indexing (H3), event streaming (Kafka), and sub-minute order fulfillment.",
        "interview_angles": [
            "Geospatial queries, ride matching, and dynamic surge pricing under adverse weather.",
            "Event-driven architecture using Kafka partitioned by geo-hexagons.",
            "Resilience against third-party notification outages (SMS, Push gateways)."
        ]
    },
    "postman": {
        "domain": "postman.com",
        "archetype": "Developer Tools Unicorn",
        "scale_estimate": "1,000-2,000 employees",
        "primary_engineering_focus": "API ecosystem, high-throughput collaborative synchronization, multi-cloud workspaces, and API testing runtime.",
        "interview_angles": [
            "Real-time state synchronization across distributed web and desktop clients.",
            "API design governance, schema-driven validation, and open-source tooling.",
            "Designing extensible plugin architectures and headless execution runtimes (Newman)."
        ]
    },
    "browserstack": {
        "domain": "browserstack.com",
        "archetype": "Developer Infrastructure & Cloud Testing",
        "scale_estimate": "1,000-2,500 employees",
        "primary_engineering_focus": "Real device cloud automation, virtualization at scale, secure tunneling, and low-latency browser streaming.",
        "interview_angles": [
            "Resource scheduling and device reclamation for thousands of concurrent test sessions.",
            "Secure peer-to-peer web tunneling with minimal latency overhead.",
            "Real-time video encoding and frame streaming over WebRTC/WebSockets."
        ]
    }
}


class CompanyResearcher:
    """
    Synthesizes public domain signals and architectural profile for a hiring company.
    """

    def extract_domain_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            # Clean common prefixes and ATS hostnames
            netloc = re.sub(r"^(?:www\.|jobs\.|careers\.|apply\.)", "", netloc)
            parts = netloc.split(".")
            if len(parts) >= 2:
                # If hosted on greenhouse.io or lever.co or ashbyhq.com, parse path
                if "greenhouse.io" in netloc or "lever.co" in netloc or "ashbyhq.com" in netloc:
                    path_parts = [p for p in parsed.path.split("/") if p]
                    if path_parts:
                        return f"{path_parts[0]}.com"
                return ".".join(parts[-2:])
            return netloc
        except Exception:
            return None

    def infer_archetype_from_signals(self, text: str) -> str:
        t = text.lower()
        if any(w in t for w in ["fintech", "payment", "banking", "lending", "credit"]):
            return "Fintech & Financial Infrastructure"
        elif any(w in t for w in ["health", "clinical", "patient", "medical"]):
            return "HealthTech & Clinical Systems"
        elif any(w in t for w in ["ecommerce", "e-commerce", "retail", "marketplace", "logistics"]):
            return "E-Commerce & Supply Chain Logistics"
        elif any(w in t for w in ["llm", "generative ai", "model training", "inference", "rag", "ai platform"]):
            return "AI/ML Product & Infrastructure"
        elif any(w in t for w in ["saas", "b2b", "crm", "workflow", "enterprise"]):
            return "B2B SaaS & Enterprise Workflow"
        elif any(w in t for w in ["security", "cyber", "identity", "auth", "compliance"]):
            return "Security & Identity Infrastructure"
        else:
            return "Software & Cloud Technology"

    def research_company(
        self,
        company: str,
        job_title: str = "",
        job_url: str = "",
        description: str = "",
    ) -> Dict[str, Any]:
        """
        Synthesizes company intelligence using curated profiles or dynamic heuristic signals.
        """
        comp_key = company.strip().lower()

        # Check known company registry
        for known_name, profile in KNOWN_COMPANIES.items():
            if known_name in comp_key or comp_key in known_name:
                return {
                    "company": company,
                    "domain": profile["domain"],
                    "archetype": profile["archetype"],
                    "scale_estimate": profile["scale_estimate"],
                    "primary_engineering_focus": profile["primary_engineering_focus"],
                    "interview_angles": profile["interview_angles"],
                    "is_curated": True
                }

        # Dynamic heuristic research
        inferred_domain = self.extract_domain_from_url(job_url) or f"{re.sub(r'[^a-zA-Z0-9]', '', comp_key)}.com"
        combined_text = f"{company} {job_title} {description}"
        archetype = self.infer_archetype_from_signals(combined_text)

        # Scale estimation
        scale = "50-250 employees (Growth Stage)"
        if any(w in combined_text.lower() for w in ["enterprise", "global", "fortune", "thousands of"]):
            scale = "1,000+ employees (Established Enterprise)"
        elif any(w in combined_text.lower() for w in ["seed", "stealth", "early stage", "founding engineer"]):
            scale = "10-50 employees (Early Stage)"

        interview_angles = [
            f"Scalability & Data Volume: How the engineering team addresses growing data volume and concurrency in {archetype}.",
            "API Architecture & Schema Evolution: Managing backward-compatible API contracts and service boundaries as the product expands.",
            "Testing & CI Reliability: Ensuring sub-minute deployment pipelines and rigorous test coverage without staging environment bottlenecks."
        ]

        return {
            "company": company,
            "domain": inferred_domain,
            "archetype": archetype,
            "scale_estimate": scale,
            "primary_engineering_focus": f"Building scalable, high-availability backend services and reliable distributed systems for {archetype.lower()}.",
            "interview_angles": interview_angles,
            "is_curated": False
        }
