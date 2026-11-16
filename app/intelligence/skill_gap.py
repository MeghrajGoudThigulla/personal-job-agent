"""
Skill Gap Detector and Upskill Roadmap Engine.
Analyzes tech deficits between job postings and the candidate's authentic profile,
and generates actionable bridging strategies, adjacent skill bridges, and market trend insights.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional
from app.intelligence.stair_matcher import StairMatcher


# Curated bridging strategies and quick proof-of-concept projects for high-frequency industry gaps
SKILL_BRIDGING_KNOWLEDGE_BASE: Dict[str, Dict[str, str]] = {
    "kubernetes": {
        "category": "Cloud & Infrastructure",
        "adjacent_skill": "Docker & Container Orchestration",
        "bridging_talking_point": "Highlight your experience containerizing multi-service FastAPI and PostgreSQL stacks with Docker Compose, health checks, and resource limits.",
        "quick_poc": "Deploy a local multi-replica FastAPI service using Minikube / K3s with Horizontal Pod Autoscaling and ConfigMaps.",
        "interview_focus": "Pod lifecycle, Service types (ClusterIP, NodePort), Ingress controllers, and persistent volume claims.",
    },
    "k8s": {
        "category": "Cloud & Infrastructure",
        "adjacent_skill": "Docker & Container Orchestration",
        "bridging_talking_point": "Highlight your experience containerizing multi-service FastAPI and PostgreSQL stacks with Docker Compose, health checks, and resource limits.",
        "quick_poc": "Deploy a local multi-replica FastAPI service using Minikube / K3s with Horizontal Pod Autoscaling and ConfigMaps.",
        "interview_focus": "Pod lifecycle, Service types, Ingress controllers, and Horizontal Pod Autoscalers.",
    },
    "kafka": {
        "category": "Distributed Systems & Streaming",
        "adjacent_skill": "Redis Pub/Sub & Celery Task Queues",
        "bridging_talking_point": "Bridge through your deep understanding of asynchronous decoupled architectures, message durability, and idempotency using Redis and Celery.",
        "quick_poc": "Build an event-driven audit logging pipeline using Kafka producer/consumer with aiokafka in FastAPI.",
        "interview_focus": "Partitioning, consumer group rebalancing, offset commits, and at-least-once vs exactly-once semantics.",
    },
    "rabbitmq": {
        "category": "Message Queues",
        "adjacent_skill": "Celery & Redis Brokers",
        "bridging_talking_point": "Demonstrate understanding of task queue routing, acknowledgment timeouts, and retry backoffs from Celery worker architectures.",
        "quick_poc": "Implement dead-letter exchange (DLX) and delayed retry queues with aio-pika.",
        "interview_focus": "Exchanges (Direct, Topic, Fanout), channel multiplexing, and consumer acknowledgments.",
    },
    "graphql": {
        "category": "API Protocols",
        "adjacent_skill": "FastAPI, REST & Pydantic Schema Modeling",
        "bridging_talking_point": "Leverage your strict Pydantic type safety and query optimization experience to explain resolver efficiency and n+1 query mitigation.",
        "quick_poc": "Create a Strawberry GraphQL schema layered over SQLAlchemy async models with DataLoader.",
        "interview_focus": "Schema-first vs code-first design, DataLoader batching to prevent N+1 queries, and mutation idempotency.",
    },
    "grpc": {
        "category": "High-Performance RPC",
        "adjacent_skill": "Protobuf & Sub-100ms API Latency Optimization",
        "bridging_talking_point": "Explain performance optimizations for inter-service communication, binary serialization, and HTTP/2 multiplexing.",
        "quick_poc": "Implement a gRPC microservice in Python with async streaming handlers and Protobuf contract definitions.",
        "interview_focus": "Protocol Buffers syntax, unary vs streaming RPCs, and gRPC interceptors for auth/tracing.",
    },
    "aws": {
        "category": "Cloud Platforms",
        "adjacent_skill": "Linux, Docker & Supabase Cloud",
        "bridging_talking_point": "Emphasize familiarity with cloud infrastructure patterns, environment isolation, IAM principles, and managed database services.",
        "quick_poc": "Provision an ECS Fargate service with RDS Postgres and an Application Load Balancer via Terraform.",
        "interview_focus": "ECS/EKS container deployments, S3 presigned URLs, SQS/SNS decoupling, and IAM least-privilege policies.",
    },
    "gcp": {
        "category": "Cloud Platforms",
        "adjacent_skill": "Cloud Run & Docker Deployments",
        "bridging_talking_point": "Reference experience deploying containerized applications with automated scale-to-zero and managed SQL instances.",
        "quick_poc": "Deploy a containerized FastAPI application to Cloud Run connected to Cloud SQL via unix domain socket.",
        "interview_focus": "Cloud Run concurrency settings, Cloud Pub/Sub push vs pull subscriptions, and Secret Manager.",
    },
    "terraform": {
        "category": "Infrastructure as Code",
        "adjacent_skill": "Docker Compose & Automated Schemas",
        "bridging_talking_point": "Draw parallels between declarative schema migrations (Alembic) and declarative infrastructure state management.",
        "quick_poc": "Write a Terraform module to provision a VPC, subnets, and an isolated database cluster on AWS or DigitalOcean.",
        "interview_focus": "State file management, remote backends with locking, terraform plan validation, and modules.",
    },
    "ci/cd": {
        "category": "DevOps & Automation",
        "adjacent_skill": "GitHub Actions & Automated Pytest Suites",
        "bridging_talking_point": "Showcase your GitHub Actions workflows executing linting, compilation, and 100+ pytest suites with multi-environment matrix testing.",
        "quick_poc": "Add automated Docker build-and-push workflow with semantic tagging and vulnerability scanning (Trivy).",
        "interview_focus": "Caching dependencies in runners, branch protection rules, zero-downtime deployment strategies (blue/green, rolling).",
    },
    "elasticsearch": {
        "category": "Search & Indexing",
        "adjacent_skill": "PostgreSQL Full-Text Search & Index Tuning",
        "bridging_talking_point": "Highlight experience optimizing PostgreSQL GIN/GiST indexes and full-text search operators for sub-100ms query performance.",
        "quick_poc": "Index job descriptions in Elasticsearch/OpenSearch with BM25 scoring and multi-field keyword analyzers.",
        "interview_focus": "Inverted index architecture, analyzer pipelines (tokenizers/stemmers), sharding, and cluster health.",
    },
    "langchain": {
        "category": "Generative AI & LLM Orchestration",
        "adjacent_skill": "UnifiedLLMClient & Anti-Slop Validation",
        "bridging_talking_point": "Detail hands-on experience building custom multi-provider LLM pipelines, prompt guards, and output sanitization systems without excessive library overhead.",
        "quick_poc": "Implement a retrieval-augmented generation (RAG) chain with LangChain LCEL and local FAISS vector store.",
        "interview_focus": "LCEL syntax, conversational memory buffers, structured output parsers, and prompt template composition.",
    },
    "llamaindex": {
        "category": "Data Frameworks for LLMs",
        "adjacent_skill": "RAG, Embeddings & Document Ingest",
        "bridging_talking_point": "Reference experience parsing unstructured PDFs, chunking documents, and generating dense vector representations for STAIR matching.",
        "quick_poc": "Build a document Q&A engine indexing candidate project repositories using VectorStoreIndex.",
        "interview_focus": "Document node parsing, sentence window retrieval, and reranking strategies.",
    },
}


class SkillGapDetector:
    """
    Detects skill gaps and provides strategic bridging roadmaps.
    """

    def __init__(self):
        self.matcher = StairMatcher()

    def analyze_job(
        self,
        job_title: str,
        description: str,
        matched_skills: Optional[List[str]] = None,
        missing_skills: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Analyzes skill gaps for a single job posting, mapping missing technologies
        to concrete bridging strategies.
        """
        m_skills = [s.lower() for s in (matched_skills or [])]
        raw_missing = [s.lower() for s in (missing_skills or [])]

        # If missing_skills is empty, scan description for common gap skills not in matched
        if not raw_missing:
            for skill_name in SKILL_BRIDGING_KNOWLEDGE_BASE:
                if (
                    skill_name not in m_skills
                    and StairMatcher.match_skill(skill_name, description)
                ):
                    raw_missing.append(skill_name)

        identified_gaps = []
        for skill in raw_missing:
            kb_entry = SKILL_BRIDGING_KNOWLEDGE_BASE.get(skill)
            if kb_entry:
                identified_gaps.append({
                    "skill": skill.upper() if len(skill) <= 4 else skill.title(),
                    "category": kb_entry["category"],
                    "adjacent_skill": kb_entry["adjacent_skill"],
                    "bridging_talking_point": kb_entry["bridging_talking_point"],
                    "quick_poc": kb_entry["quick_poc"],
                    "interview_focus": kb_entry["interview_focus"],
                })
            else:
                identified_gaps.append({
                    "skill": skill.upper() if len(skill) <= 4 else skill.title(),
                    "category": "Specialized Tool / Framework",
                    "adjacent_skill": "Python / Backend Engineering Architecture",
                    "bridging_talking_point": f"Emphasize your core systems foundation, rapid technology absorption, and hands-on ability to master {skill} in production.",
                    "quick_poc": f"Create a standalone proof-of-concept exploring {skill} integration with an async FastAPI backend.",
                    "interview_focus": f"Architecture fundamentals, configuration patterns, and failure modes of {skill}.",
                })

        return {
            "job_title": job_title,
            "total_matched": len(m_skills),
            "matched_skills": [s.title() for s in m_skills],
            "total_gaps": len(identified_gaps),
            "gaps": identified_gaps,
        }

    def aggregate_market_gaps(self, job_metadata_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Aggregates missing skill occurrences across multiple job postings to find
        the highest-ROI skills to learn next.
        """
        gap_counter: Counter[str] = Counter()
        total_jobs = len(job_metadata_list)

        for meta in job_metadata_list:
            missing = meta.get("missing_skills", [])
            for s in missing:
                clean = s.strip().lower()
                if clean:
                    gap_counter[clean] += 1

        ranked = []
        for skill, count in gap_counter.most_common(12):
            kb = SKILL_BRIDGING_KNOWLEDGE_BASE.get(skill, {})
            pct = round((count / total_jobs * 100), 1) if total_jobs else 0.0
            ranked.append({
                "skill": skill.upper() if len(skill) <= 4 else skill.title(),
                "demand_count": count,
                "prevalence_pct": pct,
                "category": kb.get("category", "General Tech"),
                "adjacent_skill": kb.get("adjacent_skill", "Backend Architecture"),
                "quick_poc": kb.get("quick_poc", f"Build a prototype integrating {skill} with your stack."),
            })

        return ranked
