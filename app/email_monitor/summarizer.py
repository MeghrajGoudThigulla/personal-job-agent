"""
Job Email Categorizer & AI Summarizer.
Classifies incoming job-related emails from Gmail/Outlook into actionable categories:
- INTERVIEW_INVITE (Urgent 🚨)
- ASSESSMENT_TEST (Urgent 📝)
- OFFER (Urgent 🎉)
- REJECTION (Informational ℹ️)
- STATUS_UPDATE (Informational ✉️)
Reads emails using UnifiedLLMClient with robust deterministic fallback to produce
dense, fact-filled AI executive summaries and batch pipeline briefings.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from app.intelligence.llm_client import UnifiedLLMClient

logger = logging.getLogger("personal_job_agent.email_monitor.summarizer")

MEETING_LINK_PATTERN = re.compile(
    r"https?://(?:[\w.-]+)?(?:zoom\.us|meet\.google\.com|teams\.microsoft\.com|calendly\.com|chilipiper\.com)[^\s<>\"')\]]+",
    re.IGNORECASE,
)
TEST_LINK_PATTERN = re.compile(
    r"https?://(?:[\w.-]+)?(?:hackerrank\.com|codility\.com|codesignal\.com|testgorilla\.com|coderbyte\.com|glider\.ai)[^\s<>\"')\]]+",
    re.IGNORECASE,
)

INTERVIEW_KEYWORDS = [
    r"\binterview\b",
    r"\binvitation\s+to\s+interview\b",
    r"\btechnical\s+round\b",
    r"\bsystem\s+design\b",
    r"\bscreening\s+call\b",
    r"\bvideo\s+call\b",
    r"\bschedule\s+(?:a\s+time|your\s+call|your\s+interview)\b",
    r"\bcalendly\.com\b",
]

ASSESSMENT_KEYWORDS = [
    r"\bassessment\b",
    r"\bhackerrank\b",
    r"\bcodility\b",
    r"\bcodesignal\b",
    r"\btake-home\b",
    r"\bcoding\s+challenge\b",
    r"\bonline\s+test\b",
    r"\btestgorilla\b",
]

OFFER_KEYWORDS = [
    r"\boffer\s+letter\b",
    r"\bjob\s+offer\b",
    r"\bdelighted\s+to\s+offer\b",
    r"\bpleased\s+to\s+offer\b",
    r"\bformal\s+offer\b",
]

REJECTION_KEYWORDS = [
    r"\bregret\s+to\s+inform\b",
    r"\bnot\s+moving\s+forward\b",
    r"\bother\s+candidates\b",
    r"\bunfortunately\b",
    r"\bdecided\s+to\s+pursue\b",
    r"\bwill\s+not\s+be\s+moving\b",
]


class EmailSummarizer:
    """Classifies hiring emails and produces intelligent AI summaries."""

    @classmethod
    def classify(cls, subject: str, body: str) -> Dict[str, Any]:
        """
        Classifies email content into a category and extracts links & urgency.
        """
        combined = f"{subject}\n{body}".lower()

        # Check offer first
        if any(re.search(p, combined) for p in OFFER_KEYWORDS):
            category = "OFFER"
            urgency = "HIGH"
            badge = "🎉 OFFER LETTER RECEIVED"
        # Check rejection before interview, as rejection emails often say "thank you for interviewing"
        elif any(re.search(p, combined) for p in REJECTION_KEYWORDS):
            category = "REJECTION"
            urgency = "NORMAL"
            badge = "ℹ️ APPLICATION STATUS UPDATE"
        # Check assessment
        elif any(re.search(p, combined) for p in ASSESSMENT_KEYWORDS):
            category = "ASSESSMENT_TEST"
            urgency = "HIGH"
            badge = "📝 TECHNICAL ASSESSMENT INVITATION"
        # Check interview
        elif any(re.search(p, combined) for p in INTERVIEW_KEYWORDS):
            category = "INTERVIEW_INVITE"
            urgency = "HIGH"
            badge = "🚨 INTERVIEW INVITATION"
        else:
            category = "STATUS_UPDATE"
            urgency = "NORMAL"
            badge = "✉️ RECRUITING UPDATE"

        # Extract links
        meeting_links = list(set(MEETING_LINK_PATTERN.findall(body)))
        test_links = list(set(TEST_LINK_PATTERN.findall(body)))

        # Clean snippet
        snippet_lines = [line.strip() for line in body.splitlines() if line.strip() and not line.startswith(">")]
        snippet = " ".join(snippet_lines[:3])[:350]

        return {
            "category": category,
            "urgency": urgency,
            "badge": badge,
            "meeting_links": meeting_links,
            "test_links": test_links,
            "snippet": snippet,
        }

    @classmethod
    def _deterministic_heuristic_summary(
        cls,
        subject: str,
        body: str,
        sender: str,
        category: str,
    ) -> str:
        """
        Rule-based high-accuracy summary generator when LLM is offline or in mock test.
        """
        # 1. Company extraction from subject or sender
        company = "Company"
        comp_match = re.search(r"(?:at|with|from)\s+([A-Z][A-Za-z0-9&.-]+(?:\s+[A-Z][A-Za-z0-9&.-]+)?)", subject)
        if comp_match:
            company = comp_match.group(1).strip()
        elif "@" in sender:
            domain_part = sender.split("@")[-1].split(".")[0].capitalize()
            if domain_part.lower() not in {"gmail", "outlook", "yahoo", "hotmail"}:
                company = domain_part

        # 2. Extract deadlines or timeframes
        deadline = "Not specified"
        time_match = re.search(r"(?:within\s+\d+\s+(?:hours|days)|by\s+[A-Za-z]+,\s+[A-Za-z]+\s+\d+|by\s+[A-Za-z]+\s+\d+)", body, re.IGNORECASE)
        if time_match:
            deadline = time_match.group(0).strip()

        # 3. Decision / Status text
        if category == "INTERVIEW_INVITE":
            action = f"Invited to interview round at {company}. Schedule via meeting link."
            req = f"Select convenient slot ({deadline})."
        elif category == "ASSESSMENT_TEST":
            action = f"Technical assessment assigned by {company}."
            req = f"Complete challenge ({deadline})."
        elif category == "OFFER":
            action = f"Official employment offer received from {company}!"
            req = "Review compensation terms and response deadline."
        elif category == "REJECTION":
            action = f"Application at {company} will not be moving forward."
            req = "Archived; focus on remaining active pipeline."
        else:
            action = f"Recruitment correspondence received regarding {subject}."
            req = "Review details in inbox."

        return (
            f"• **Entity & Context:** {company} ({subject})\n"
            f"• **Status / Event:** {action}\n"
            f"• **Action Required:** {req}"
        )

    @classmethod
    async def summarize_email(
        cls,
        subject: str,
        body: str,
        sender: str = "",
        llm_client: Optional[UnifiedLLMClient] = None,
    ) -> str:
        """
        Reads and produces a concise AI executive summary of an individual recruitment email.
        """
        classification = cls.classify(subject, body)
        category = classification["category"]

        client = llm_client or UnifiedLLMClient()
        prompt = (
            f"Analyze this job applicant email and produce a 3-bullet point executive summary for the candidate:\n"
            f"- Bullet 1: Company & Role context\n"
            f"- Bullet 2: Key message (interview scheduled, coding challenge, offer, or rejection)\n"
            f"- Bullet 3: Action required and deadline\n\n"
            f"From: {sender}\n"
            f"Subject: {subject}\n"
            f"Content:\n{body[:2500]}\n\n"
            f"Keep summary strictly under 85 words, objective, and dense with facts."
        )
        system_prompt = "You are an executive career assistant for a software engineer. Provide a structured 3-bullet executive summary."

        try:
            res = await client.generate_completion(
                system_prompt=system_prompt,
                user_prompt=prompt,
                temperature=0.1,
                max_tokens=220,
            )
            if res and res != "HEURISTIC_GENERATION" and len(res.strip()) > 20:
                return res.strip()
        except Exception as e:
            logger.debug(f"LLM email summary failed, using heuristic: {e}")

        return cls._deterministic_heuristic_summary(subject, body, sender, category)

    @classmethod
    async def summarize_inbox_batch(
        cls,
        emails: List[Dict[str, Any]],
        llm_client: Optional[UnifiedLLMClient] = None,
    ) -> str:
        """
        Synthesizes an aggregated briefing summarizing all received hiring emails in a cycle or day.
        """
        if not emails:
            return "No recent recruitment emails to summarize."

        urgent_count = sum(1 for e in emails if e.get("classification", {}).get("urgency") == "HIGH")
        categories_breakdown = {}
        for e in emails:
            cat = e.get("classification", {}).get("category", "STATUS_UPDATE")
            categories_breakdown[cat] = categories_breakdown.get(cat, 0) + 1

        email_previews = []
        for e in emails[:12]:
            sender = e.get("sender", "Unknown")
            subject = e.get("subject", "No subject")
            cat = e.get("classification", {}).get("category", "")
            email_previews.append(f"- [{cat}] From: {sender} | Subject: {subject}")

        preview_text = "\n".join(email_previews)

        client = llm_client or UnifiedLLMClient()
        prompt = (
            f"Synthesize an aggregated executive briefing for a software engineer based on these {len(emails)} received job emails:\n\n"
            f"{preview_text}\n\n"
            f"Provide:\n"
            f"1. Executive Overview (1-2 sentences on current hiring activity)\n"
            f"2. Urgent Action Items (interviews/assessments requiring immediate candidate response)\n"
            f"3. General Status & Follow-ups\n"
            f"Keep it under 150 words."
        )
        system_prompt = "You are an executive talent strategist. Synthesize an aggregated recruitment inbox briefing."

        try:
            res = await client.generate_completion(
                system_prompt=system_prompt,
                user_prompt=prompt,
                temperature=0.2,
                max_tokens=300,
            )
            if res and res != "HEURISTIC_GENERATION" and len(res.strip()) > 30:
                return res.strip()
        except Exception as e:
            logger.debug(f"LLM batch summary failed, using heuristic: {e}")

        # Deterministic batch summary fallback
        breakdown_str = ", ".join(f"{k.replace('_', ' ').title()}: {v}" for k, v in categories_breakdown.items())
        return (
            f"📊 **Recruitment Pipeline Activity ({len(emails)} Updates Received)**\n\n"
            f"• **Breakdown:** {breakdown_str}\n"
            f"• **Urgent Actions:** {urgent_count} item(s) require immediate scheduling or test submission.\n"
            f"• **Recommended Action:** Check meeting invitations and assessment deadlines in your inbox first."
        )

    @classmethod
    def format_telegram_alert(
        cls,
        account: str,
        sender: str,
        subject: str,
        date_str: str,
        classification: Dict[str, Any],
        summary_text: Optional[str] = None,
    ) -> str:
        """Formats the classified email with its AI executive summary into a Telegram alert."""
        badge = classification.get("badge", "✉️ RECRUITING UPDATE")
        category = classification.get("category", "STATUS_UPDATE")
        summary = summary_text or classification.get("summary") or classification.get("snippet", "")
        meeting_links: List[str] = classification.get("meeting_links", [])
        test_links: List[str] = classification.get("test_links", [])

        text = (
            f"*{badge}*\n\n"
            f"📬 *Account:* `{account}`\n"
            f"👤 *From:* {sender}\n"
            f"📌 *Subject:* {subject}\n"
            f"📅 *Date:* {date_str}\n"
            f"🏷️ *Category:* `{category}`\n\n"
            f"💡 *AI Executive Summary:*\n{summary}\n"
        )

        if meeting_links:
            text += "\n🗓️ *Meeting Links:*\n"
            for link in meeting_links[:2]:
                text += f"• [Join Meeting / Schedule]({link})\n"

        if test_links:
            text += "\n💻 *Test Links:*\n"
            for link in test_links[:2]:
                text += f"• [Open Assessment Portal]({link})\n"

        text += "\n⚡ *Action:* Respond or schedule before candidate cutoff."
        return text

    @classmethod
    def format_inbox_digest(cls, emails: List[Dict[str, Any]], batch_summary: str) -> str:
        """Formats an aggregated briefing across multiple received emails into a single Telegram message."""
        count = len(emails)
        text = (
            f"📬 *RECRUITMENT INBOX DIGEST ({count} Updates Received)*\n\n"
            f"{batch_summary}\n\n"
            f"🔗 *Recent Email Subjects:*\n"
        )
        for e in emails[:6]:
            cat = e.get("classification", {}).get("category", "")
            subj = e.get("subject", "Email")
            text += f"• `{cat}`: {subj[:55]}\n"

        text += "\n🔍 *All emails processed and categorized by your Personal Job Agent.*"
        return text
