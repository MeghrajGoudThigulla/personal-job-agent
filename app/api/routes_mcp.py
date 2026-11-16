"""
Model Context Protocol (MCP) JSON-RPC 2.0 Endpoint.
Enables AI agents (Claude Code, Cursor, Antigravity, LLM tools) to query job postings,
generate tailored cover letters, run interview prep, update application statuses,
and retrieve pipeline intelligence.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer
from app.api.routes_analytics import get_analytics_funnel
from app.core.clock import utcnow
from app.core.database import get_db
from app.core.models import JobPosting
from app.intelligence.cover_letter import CoverLetterGenerator
from app.intelligence.interview_prep import InterviewPrepGenerator
from app.intelligence.skill_gap import SkillGapDetector

logger = logging.getLogger("personal_job_agent.api.mcp")

router = APIRouter(prefix="/api/mcp", tags=["MCP"])


MCP_TOOLS_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "search_jobs",
        "description": "Search discovered job postings with filters for status, minimum STAIR match score, source platform, and search keyword.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword to search in job title, company, or category."},
                "min_score": {"type": "number", "description": "Minimum STAIR match score (0-100). Default 70."},
                "status": {"type": "string", "description": "Workflow status: 'all', 'new', 'reviewed', 'applied', 'interviewing', 'offer', 'rejected'."},
                "source": {"type": "string", "description": "Source platform: 'all', 'Naukri', 'LinkedIn', 'Indeed', 'Ashby', 'Greenhouse', 'Lever'."},
                "limit": {"type": "integer", "description": "Maximum number of jobs to return (default 10, max 50)."}
            }
        }
    },
    {
        "name": "get_job_details",
        "description": "Retrieve comprehensive details for a specific job posting, including full description, match score, and identified skills.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "integer", "description": "The unique integer ID of the job posting."}
            },
            "required": ["job_id"]
        }
    },
    {
        "name": "generate_cover_letter",
        "description": "Generate a concise, metric-dense, text-only cover letter (<200 words) tailored to a specific job and adhering to Anti-Slop guidelines.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "integer", "description": "The unique integer ID of the job posting."}
            },
            "required": ["job_id"]
        }
    },
    {
        "name": "generate_interview_prep",
        "description": "Generate a structured interview prep pack containing technical questions, STAR behavioral frameworks, and reverse questions for interviewers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "integer", "description": "The unique integer ID of the job posting."}
            },
            "required": ["job_id"]
        }
    },
    {
        "name": "analyze_skill_gaps",
        "description": "Analyze missing technologies for a specific job posting and return concrete architectural bridging strategies and proof-of-concept ideas.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "integer", "description": "The unique integer ID of the job posting."}
            },
            "required": ["job_id"]
        }
    },
    {
        "name": "research_company",
        "description": "Research public domain signals, architectural archetype, and strategic interview discussion angles for a job posting.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "integer", "description": "The unique integer ID of the job posting."}
            },
            "required": ["job_id"]
        }
    },
    {
        "name": "benchmark_salary",
        "description": "Extract stated salary and estimate market compensation bands (INR Lakhs / USD) for a job posting.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "integer", "description": "The unique integer ID of the job posting."}
            },
            "required": ["job_id"]
        }
    },


    {
        "name": "update_application_stage",
        "description": "Update the Kanban application stage, status, or notes for a job posting.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "integer", "description": "The unique integer ID of the job posting."},
                "status": {"type": "string", "description": "New status: 'applied', 'interviewing', 'offer', 'rejected', 'archived'."},
                "interview_stage": {"type": "string", "description": "Interview round name, e.g. 'Screening', 'Technical Round 1', 'System Design', 'Final HR'."},
                "notes": {"type": "string", "description": "Application or interview notes."}
            },
            "required": ["job_id", "status"]
        }
    },
    {
        "name": "get_pipeline_analytics",
        "description": "Get high-level recruitment funnel metrics, stage conversion rates, and performance breakdowns across job sources.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "summarize_recruitment_emails",
        "description": "Reads recent candidate correspondence from connected Gmail & Outlook inboxes and generates an AI executive summary of all interviews, assessments, and application decisions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of recent emails to analyze (default 15)."}
            }
        }
    }
]


class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Any] = None
    method: str
    params: Optional[Dict[str, Any]] = Field(default_factory=dict)


@router.get("/tools")
async def list_mcp_tools():
    """Returns tool schemas in plain JSON for agent discoverability."""
    return {"tools": MCP_TOOLS_DEFINITIONS}


@router.post("")
async def handle_mcp_jsonrpc(
    rpc_request: JSONRPCRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Standard MCP JSON-RPC 2.0 handler supporting initialize, ping,
    tools/list, and tools/call.
    """
    req_id = rpc_request.id
    method = rpc_request.method
    params = rpc_request.params or {}

    try:
        # 1. MCP Initialization
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "personal-job-agent-mcp",
                        "version": "1.0.0"
                    }
                }
            }

        # 2. Ping
        if method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        # 3. Tools Listing
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": MCP_TOOLS_DEFINITIONS}
            }

        # 4. Tool Execution
        if method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})

            content_text = await _execute_tool(tool_name, args, db)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": content_text}],
                    "isError": False
                }
            }

        # Unknown method
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        }

    except Exception as e:
        logger.exception(f"Error handling MCP request {method}: {e}")
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": f"Error executing tool: {str(e)}"}],
                "isError": True
            }
        }


async def _execute_tool(tool_name: str, args: Dict[str, Any], db: AsyncSession) -> str:
    """Executes an individual tool and formats result as a string."""
    if tool_name == "search_jobs":
        min_score = args.get("min_score", 70.0)
        status = args.get("status", "all")
        source = args.get("source", "all")
        query_text = args.get("query")
        limit = min(int(args.get("limit", 10)), 50)

        stmt = select(JobPosting).options(defer(JobPosting.description))
        if status != "all":
            stmt = stmt.where(JobPosting.status == status)
        if source != "all":
            stmt = stmt.where(JobPosting.source_platform.ilike(f"%{source}%"))
        if min_score is not None:
            stmt = stmt.where(JobPosting.match_score >= float(min_score))
        if query_text:
            pattern = f"%{query_text}%"
            stmt = stmt.where((JobPosting.title.ilike(pattern)) | (JobPosting.company.ilike(pattern)))

        stmt = stmt.order_by(desc(JobPosting.match_score)).limit(limit)
        res = await db.execute(stmt)
        jobs = res.scalars().all()

        results = []
        for j in jobs:
            results.append({
                "id": j.id,
                "title": j.title,
                "company": j.company,
                "location": j.location,
                "source": j.source_platform,
                "match_score": j.match_score,
                "status": j.status,
                "url": j.url
            })
        return json.dumps(results, indent=2)

    elif tool_name == "get_job_details":
        job_id = int(args.get("job_id", 0))
        stmt = select(JobPosting).where(JobPosting.id == job_id)
        res = await db.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            return f"Job with id {job_id} not found."
        return json.dumps(job.to_dict(include_description=True), indent=2)

    elif tool_name == "generate_cover_letter":
        job_id = int(args.get("job_id", 0))
        stmt = select(JobPosting).where(JobPosting.id == job_id)
        res = await db.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            return f"Job with id {job_id} not found."

        matched_skills = []
        if job.match_reason:
            try:
                m_data = json.loads(job.match_reason) if isinstance(job.match_reason, str) else job.match_reason
                matched_skills = m_data.get("matched_skills", [])
            except Exception:
                pass

        gen = CoverLetterGenerator()
        letter = await gen.generate(
            job_title=job.title,
            company=job.company,
            description=job.description or "",
            matched_skills=matched_skills
        )
        return letter

    elif tool_name == "generate_interview_prep":
        job_id = int(args.get("job_id", 0))
        stmt = select(JobPosting).where(JobPosting.id == job_id)
        res = await db.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            return f"Job with id {job_id} not found."

        matched_skills = []
        if job.match_reason:
            try:
                m_data = json.loads(job.match_reason) if isinstance(job.match_reason, str) else job.match_reason
                matched_skills = m_data.get("matched_skills", [])
            except Exception:
                pass

        prep_gen = InterviewPrepGenerator()
        prep = await prep_gen.generate(
            job_title=job.title,
            company=job.company,
            description=job.description or "",
            matched_skills=matched_skills
        )
        return prep.get("markdown", json.dumps(prep, indent=2))

    elif tool_name == "analyze_skill_gaps":
        job_id = int(args.get("job_id", 0))
        stmt = select(JobPosting).where(JobPosting.id == job_id)
        res = await db.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            return f"Job with id {job_id} not found."

        matched_skills = []
        missing_skills = []
        if job.match_reason:
            try:
                m_data = json.loads(job.match_reason) if isinstance(job.match_reason, str) else job.match_reason
                matched_skills = m_data.get("matched_skills", [])
                missing_skills = m_data.get("missing_skills", [])
            except Exception:
                pass

        detector = SkillGapDetector()
        analysis = detector.analyze_job(
            job_title=job.title,
            description=job.description or "",
            matched_skills=matched_skills,
            missing_skills=missing_skills
        )
        return json.dumps(analysis, indent=2)

    elif tool_name == "research_company":
        job_id = int(args.get("job_id", 0))
        stmt = select(JobPosting).where(JobPosting.id == job_id)
        res = await db.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            return f"Job with id {job_id} not found."

        from app.intelligence.company_research import CompanyResearcher
        researcher = CompanyResearcher()
        research = researcher.research_company(
            company=job.company,
            job_title=job.title,
            job_url=job.url or "",
            description=job.description or ""
        )
        return json.dumps(research, indent=2)

    elif tool_name == "benchmark_salary":
        job_id = int(args.get("job_id", 0))
        stmt = select(JobPosting).where(JobPosting.id == job_id)
        res = await db.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            return f"Job with id {job_id} not found."

        from app.intelligence.salary_benchmarks import SalaryBenchmarker
        benchmarker = SalaryBenchmarker()
        bench = benchmarker.benchmark(
            job_title=job.title,
            company=job.company,
            location=job.location or "",
            description=job.description or ""
        )
        return json.dumps(bench, indent=2)



    elif tool_name == "update_application_stage":
        job_id = int(args.get("job_id", 0))
        status = args.get("status")
        interview_stage = args.get("interview_stage")
        notes = args.get("notes")

        stmt = select(JobPosting).where(JobPosting.id == job_id)
        res = await db.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            return f"Job with id {job_id} not found."

        if status:
            job.status = status
            if status == "applied" and not job.applied_at:
                job.applied_at = utcnow()
        if interview_stage:
            job.interview_stage = interview_stage
        if notes:
            job.notes = f"{job.notes}\n{notes}".strip()

        await db.commit()
        return f"Updated job {job_id}: status={job.status}, stage={job.interview_stage}"

    elif tool_name == "get_pipeline_analytics":
        funnel_data = await get_analytics_funnel(db)
        return json.dumps(funnel_data, indent=2)

    elif tool_name == "summarize_recruitment_emails":
        limit = int(args.get("limit", 15))
        from app.email_monitor.inbox_scanner import InboxScanner
        scanner = InboxScanner()
        res = await scanner.get_recent_emails_summary(limit=limit)
        return json.dumps(res, indent=2)

    else:
        raise ValueError(f"Unknown tool name: {tool_name}")
