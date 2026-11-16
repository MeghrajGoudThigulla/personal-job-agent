"""
Weekly Digest Generator and Multi-Channel Notifier.
Compiles a weekly executive summary of pipeline metrics, top high-match roles,
market skill demands, and interview statuses, delivering it via Telegram, Discord, and Slack.
"""

from __future__ import annotations

import json
from datetime import timedelta
import logging
from typing import Any, Dict
from sqlalchemy import case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.clock import utcnow
from app.core.models import JobPosting
from app.intelligence.skill_gap import SkillGapDetector
from app.notifiers.telegram import TelegramNotifier
from app.notifiers.discord import DiscordNotifier
from app.notifiers.slack import SlackNotifier

logger = logging.getLogger("personal_job_agent.notifier.weekly_digest")


class WeeklyDigestNotifier:
    """
    Generates and dispatches the weekly recruitment pipeline digest.
    """

    def __init__(self):
        self.telegram = TelegramNotifier()
        self.discord = DiscordNotifier()
        self.slack = SlackNotifier()

    async def compile_digest_data(self, db: AsyncSession, days: int = 7) -> Dict[str, Any]:
        """
        Gathers stats from the last `days` days.
        """
        since_date = utcnow() - timedelta(days=days)

        # 1. Pipeline metrics for past 7 days
        stmt_counts = select(
            func.count(JobPosting.id).label("discovered"),
            func.sum(case((JobPosting.match_score >= 70.0, 1), else_=0)).label("qualified"),
            func.sum(case((JobPosting.applied_at.isnot(None) | JobPosting.status.in_(["applied", "interviewing", "offer", "rejected"]), 1), else_=0)).label("applied"),
            func.sum(case((JobPosting.interview_stage != "none", 1), (JobPosting.status.in_(["interviewing", "offer"]), 1), else_=0)).label("interviewing"),
            func.sum(case((JobPosting.status == "offer", 1), else_=0)).label("offers"),
        ).where(JobPosting.discovered_at >= since_date)

        res_counts = await db.execute(stmt_counts)
        row = res_counts.first()

        discovered = int(row.discovered or 0)
        qualified = int(row.qualified or 0)
        applied = int(row.applied or 0)
        interviewing = int(row.interviewing or 0)
        offers = int(row.offers or 0)

        # 2. Top 3 highest-matching jobs
        stmt_top = (
            select(JobPosting)
            .where(JobPosting.discovered_at >= since_date)
            .order_by(desc(JobPosting.match_score), desc(JobPosting.discovered_at))
            .limit(3)
        )
        res_top = await db.execute(stmt_top)
        top_jobs = res_top.scalars().all()

        top_jobs_data = []
        for j in top_jobs:
            top_jobs_data.append({
                "id": j.id,
                "title": j.title,
                "company": j.company,
                "location": j.location,
                "match_score": round(j.match_score, 1),
                "url": j.url,
            })

        # 3. Market skill gaps
        stmt_gaps = (
            select(JobPosting.match_reason)
            .where(JobPosting.discovered_at >= since_date, JobPosting.match_score >= 60.0)
        )
        res_gaps = await db.execute(stmt_gaps)
        meta_list = []
        for (m_reason,) in res_gaps.all():
            if m_reason:
                try:
                    data = json.loads(m_reason) if isinstance(m_reason, str) else m_reason
                    meta_list.append(data)
                except Exception:
                    pass

        detector = SkillGapDetector()
        top_market_gaps = detector.aggregate_market_gaps(meta_list)[:3]

        return {
            "period_days": days,
            "discovered": discovered,
            "qualified": qualified,
            "applied": applied,
            "interviewing": interviewing,
            "offers": offers,
            "top_jobs": top_jobs_data,
            "top_market_gaps": top_market_gaps,
        }

    def format_telegram_digest(self, data: Dict[str, Any]) -> str:
        """
        Formats digest for Telegram (Markdown).
        """
        lines = [
            "📊 *WEEKLY JOB SEARCH & PIPELINE DIGEST*",
            f"📅 _Past {data['period_days']} Days Performance_\n",
            "📈 *Pipeline Statistics:*",
            f"• *Discovered:* {data['discovered']} opportunities",
            f"• *Qualified (≥70%):* {data['qualified']} roles",
            f"• *Applications Submitted:* {data['applied']}",
            f"• *Active Interviews:* {data['interviewing']}",
            f"• *Offers:* {data['offers']}\n",
        ]

        if data["top_jobs"]:
            lines.append("🌟 *Top High-Match Roles:*")
            for i, j in enumerate(data["top_jobs"], start=1):
                lines.append(f"{i}. *{j['title']}* @ {j['company']} ({j['match_score']}%)")
                lines.append(f"   🔗 [View Posting]({j['url']})")
            lines.append("")

        if data["top_market_gaps"]:
            lines.append("💡 *Top Market Tech In-Demand:*")
            gap_str = ", ".join([f"{g['skill']} ({g['prevalence_pct']}%)" for g in data["top_market_gaps"]])
            lines.append(f"• {gap_str}\n")

        lines.append("🎯 *Next Step:* Keep applications moving in your Kanban tracker!")
        return "\n".join(lines)

    async def dispatch_digest(self, db: AsyncSession, days: int = 7) -> Dict[str, Any]:
        """
        Compiles and sends the digest to all configured channels.
        """
        data = await self.compile_digest_data(db, days=days)
        tg_text = self.format_telegram_digest(data)

        dispatched_channels = []

        # 1. Telegram
        if self.telegram.is_configured:
            ok = await self.telegram.send_message(tg_text)
            if ok:
                dispatched_channels.append("telegram")

        # 2. Discord
        if self.discord.is_configured:
            # Discord format (plain text markdown)
            ok = await self.discord.send_message(tg_text.replace("*", "**"))
            if ok:
                dispatched_channels.append("discord")

        # 3. Slack
        if self.slack.is_configured:
            ok = await self.slack.send_message(tg_text)
            if ok:
                dispatched_channels.append("slack")

        logger.info(f"Weekly digest dispatched to channels: {dispatched_channels}")
        return {
            "success": True,
            "dispatched_channels": dispatched_channels,
            "digest_summary": data,
            "text": tg_text
        }
