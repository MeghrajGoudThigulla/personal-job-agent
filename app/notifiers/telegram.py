import asyncio
import logging
from typing import Any, Dict, List, Optional
import httpx
from app.config import settings
from app.core.trace import log_audit_event

logger = logging.getLogger("personal_job_agent.notifier.telegram")


def split_latex_chunks(code: str, max_chunk_size: int = 3400) -> List[str]:
    """
    Splits long LaTeX source code into chunks suitable for Telegram's 4096 character limit,
    preserving line integrity where possible.
    """
    if not code:
        return []
    if len(code) <= max_chunk_size:
        return [code]

    chunks: List[str] = []
    lines = code.splitlines(keepends=True)
    current_chunk: List[str] = []
    current_len = 0

    for line in lines:
        if current_len + len(line) > max_chunk_size and current_chunk:
            chunks.append("".join(current_chunk))
            current_chunk = [line]
            current_len = len(line)
        else:
            current_chunk.append(line)
            current_len += len(line)

    if current_chunk:
        chunks.append("".join(current_chunk))
    return chunks


class TelegramNotifier:
    """Sends real-time job alerts to Meghraj via Telegram Bot with sequential multi-message delivery."""

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self._override_token = bot_token
        self._override_chat_id = chat_id

    @property
    def bot_token(self) -> str:
        return self._override_token or settings.TELEGRAM_BOT_TOKEN

    @property
    def chat_id(self) -> str:
        return self._override_chat_id or settings.TELEGRAM_CHAT_ID

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    async def send_job_alert(self, job_data: Dict[str, Any]) -> bool:
        """
        Dispatches multi-part sequential alert:
        1. Primary Job Notification
        2. Subsequent Message: Anti-slop text-only Cover Letter
        3. Subsequent Message(s): Tailored Resume LaTeX code (chunked as needed)
        """
        if not self.is_configured:
            return False

        title = job_data.get("title", "Untitled Role")
        company = job_data.get("company", "Unknown Company")
        location = job_data.get("location", "Remote")
        match_score = job_data.get("match_score", 0.0)
        match_tier = job_data.get("match_tier", "P1")
        role_category = job_data.get("role_category", "Engineering")
        url = job_data.get("url", "")
        matched_skills = job_data.get("matched_skills", [])
        job_id = job_data.get("id", "")

        skills_str = ", ".join(matched_skills[:6]) if matched_skills else "Python, Backend"

        posted_str = job_data.get("posted_at_ist") or job_data.get("posted_date") or "Recently discovered"
        if job_data.get("posted_date_unverified"):
            posted_str += " (unverified date)"

        # 1. Primary Message: Job Notification
        job_alert_text = (
            f"🚀 *NEW HIGH-MATCH JOB DISCOVERED*\n\n"
            f"🏢 *Company:* {company}\n"
            f"💼 *Role:* {title}\n"
            f"📍 *Location:* {location}\n"
            f"📅 *Posted:* {posted_str}\n"
            f"🎯 *Match Score:* `{match_score}%` ({match_tier})\n"
            f"🏷️ *Category:* {role_category}\n"
            f"🛠️ *Stack Match:* {skills_str}\n\n"
            f"🔗 [Direct Apply Link]({url})"
        )

        ok = await self.send_message(job_alert_text, parse_mode="Markdown")
        if not ok:
            return False

        await log_audit_event("telegram_notification", {"job_id": job_id, "company": company}, "success")

        # 2. Subsequent Message: Cover Letter (sent separately for clean copy-paste)
        cover_letter = job_data.get("cover_letter")
        if cover_letter:
            await asyncio.sleep(0.35)
            clean_cl = str(cover_letter).replace("```", "'''").strip()
            cl_text = (
                f"📝 *Tailored Cover Letter | {company} — {title}*\n"
                f"_(Direct copy & submit ready)_\n\n"
                f"```{clean_cl}```"
            )
            await self.send_message(cl_text, parse_mode="Markdown")

        # 3. Subsequent Message(s): Tailored Resume LaTeX code
        tailored_tex = job_data.get("tailored_tex")
        if tailored_tex:
            await asyncio.sleep(0.35)
            chunks = split_latex_chunks(tailored_tex, max_chunk_size=3400)
            total_chunks = len(chunks)
            for idx, chunk in enumerate(chunks, start=1):
                part_header = f" (Part {idx}/{total_chunks})" if total_chunks > 1 else ""
                clean_chunk = chunk.replace("```", "'''")
                latex_msg = (
                    f"📄 *Tailored Resume LaTeX{part_header} | {company} — {title}*\n"
                    f"_(Copy to Overleaf or local compiler)_\n\n"
                    f"```latex\n{clean_chunk}\n```"
                )
                await self.send_message(latex_msg, parse_mode="Markdown")
                if idx < total_chunks:
                    await asyncio.sleep(0.35)

        return True

    async def send_message(self, text: str, parse_mode: Optional[str] = "Markdown") -> bool:
        """Sends an arbitrary message to Telegram, with automatic plain-text retry if markdown parsing fails."""
        if not self.is_configured:
            return False

        api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_web_page_preview": False,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(api_url, json=payload)
                res.raise_for_status()
                return True
        except httpx.HTTPStatusError as e:
            # If Telegram rejects markdown formatting (e.g. 400 Bad Request: can't parse entities)
            if parse_mode and e.response.status_code == 400:
                try:
                    payload.pop("parse_mode", None)
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        retry_res = await client.post(api_url, json=payload)
                        retry_res.raise_for_status()
                        return True
                except Exception as retry_err:
                    logger.debug(f"Retry without parse_mode failed: {retry_err}")

            raw_err = str(e)
            token = self.bot_token
            sanitized_err = raw_err.replace(token, "[REDACTED_BOT_TOKEN]") if token else raw_err
            logger.error(f"Failed to send Telegram message: {sanitized_err}")
            return False
        except Exception as e:
            raw_err = str(e)
            token = self.bot_token
            sanitized_err = raw_err.replace(token, "[REDACTED_BOT_TOKEN]") if token else raw_err
            logger.error(f"Failed to send Telegram message: {sanitized_err}")
            return False
