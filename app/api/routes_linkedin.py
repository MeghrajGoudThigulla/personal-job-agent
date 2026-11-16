from __future__ import annotations

from datetime import datetime, timezone, timedelta
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.models import LinkedInPost
from app.intelligence.linkedin_post_generator import LinkedInPostGenerator
from app.notifiers.telegram import TelegramNotifier
from app.core.trace import log_audit_event

logger = logging.getLogger("personal_job_agent.api.linkedin")
router = APIRouter(prefix="/api/linkedin", tags=["LinkedIn"])

IST = timezone(timedelta(hours=5, minutes=30))


class GeneratePostRequest(BaseModel):
    topic_override: Optional[str] = None
    theme_override: Optional[str] = None
    send_telegram: bool = True


class UpdateStatusRequest(BaseModel):
    posted: bool


@router.get("/posts")
async def get_posts(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Returns historical list of drafted LinkedIn posts."""
    query = select(LinkedInPost).order_by(desc(LinkedInPost.post_date)).offset(offset).limit(limit)
    res = await db.execute(query)
    posts = res.scalars().all()
    return [p.to_dict() for p in posts]


@router.get("/today")
async def get_todays_post(
    auto_generate: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """
    Returns today's drafted LinkedIn post.
    If no post exists for today and auto_generate is true, generates one on demand.
    """
    today_str = datetime.now(IST).strftime("%Y-%m-%d")
    query = select(LinkedInPost).where(LinkedInPost.post_date == today_str)
    res = await db.execute(query)
    post = res.scalar_one_or_none()

    if post:
        return post.to_dict()

    if not auto_generate:
        return {"post": None, "message": "No post generated yet for today."}

    # Generate on demand
    generator = LinkedInPostGenerator()
    draft = await generator.generate_daily_post()

    new_post = LinkedInPost(
        post_date=today_str,
        theme=draft["theme"],
        hook=draft["hook"],
        content=draft["content"],
        hashtags=draft["hashtags"],
        call_to_action=draft["call_to_action"],
        posted=False,
        notified_telegram=False,
    )
    db.add(new_post)
    await db.commit()
    await db.refresh(new_post)

    return new_post.to_dict()


@router.post("/generate")
async def generate_post(
    req: GeneratePostRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generates or regenerates a LinkedIn post for today.
    """
    today_str = datetime.now(IST).strftime("%Y-%m-%d")
    generator = LinkedInPostGenerator()
    draft = await generator.generate_daily_post(
        topic_override=req.topic_override,
        theme_override=req.theme_override,
    )

    # Check if a post already exists for today
    query = select(LinkedInPost).where(LinkedInPost.post_date == today_str)
    res = await db.execute(query)
    post = res.scalar_one_or_none()

    if post:
        post.theme = draft["theme"]
        post.hook = draft["hook"]
        post.content = draft["content"]
        post.hashtags = draft["hashtags"]
        post.call_to_action = draft["call_to_action"]
    else:
        post = LinkedInPost(
            post_date=today_str,
            theme=draft["theme"],
            hook=draft["hook"],
            content=draft["content"],
            hashtags=draft["hashtags"],
            call_to_action=draft["call_to_action"],
            posted=False,
            notified_telegram=False,
        )
        db.add(post)

    await db.commit()
    await db.refresh(post)

    # Dispatch to Telegram if requested
    if req.send_telegram:
        telegram = TelegramNotifier()
        if telegram.is_configured:
            msg = (
                f"📱 *DAILY LINKEDIN POST DRAFT*\n"
                f"📅 *Date:* {today_str} • *Theme:* {post.theme}\n\n"
                f"💡 *Hook:*\n_{post.hook}_\n\n"
                f"📝 *Full Post Body (Copy & Share):*\n"
                f"```{post.content}```\n\n"
                f"🏷️ *Hashtags:* {post.hashtags}\n\n"
                f"👉 [Open LinkedIn to Post](https://www.linkedin.com/feed/)"
            )
            sent = await telegram.send_message(msg, parse_mode="Markdown")
            if sent:
                post.notified_telegram = True
                await db.commit()

    return post.to_dict()


@router.patch("/posts/{post_id}/status")
async def update_post_status(
    post_id: int,
    req: UpdateStatusRequest,
    db: AsyncSession = Depends(get_db),
):
    """Marks a post as published/posted or draft."""
    post = await db.get(LinkedInPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    post.posted = req.posted
    await db.commit()
    return {"id": post.id, "posted": post.posted}


@router.post("/posts/{post_id}/send-telegram")
async def send_post_telegram(
    post_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Manually dispatches an existing drafted post to Telegram."""
    post = await db.get(LinkedInPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    telegram = TelegramNotifier()
    if not telegram.is_configured:
        raise HTTPException(status_code=400, detail="Telegram is not configured")

    msg = (
        f"📱 *DAILY LINKEDIN POST DRAFT*\n"
        f"📅 *Date:* {post.post_date} • *Theme:* {post.theme}\n\n"
        f"💡 *Hook:*\n_{post.hook}_\n\n"
        f"📝 *Full Post Body (Copy & Share):*\n"
        f"```{post.content}```\n\n"
        f"🏷️ *Hashtags:* {post.hashtags}\n\n"
        f"👉 [Open LinkedIn to Post](https://www.linkedin.com/feed/)"
    )
    sent = await telegram.send_message(msg, parse_mode="Markdown")
    if sent:
        post.notified_telegram = True
        await db.commit()
        await log_audit_event("linkedin_post_dispatched", {"post_id": post.id, "date": post.post_date}, "success")
        return {"success": True, "message": "Dispatched to Telegram"}

    raise HTTPException(status_code=500, detail="Failed to send Telegram message")

