"""
Job Email Categorizer & Summarizer.
Classifies incoming job-related emails from Gmail/Outlook into actionable categories:
- INTERVIEW_INVITE (Urgent 🚨)
- ASSESSMENT_TEST (Urgent 📝)
- OFFER (Urgent 🎉)
- REJECTION (Informational ℹ️)
- STATUS_UPDATE (Informational ✉️)
Extracts meeting/assessment links and deadlines, and formats immediate Telegram alerts.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

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
    """Classifies hiring emails and formats urgent alerts."""

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
    def format_telegram_alert(
        cls,
        account: str,
        sender: str,
        subject: str,
        date_str: str,
        classification: Dict[str, Any],
    ) -> str:
        """Formats the classified email into a markdown Telegram alert."""
        badge = classification["badge"]
        category = classification["category"]
        snippet = classification["snippet"]
        meeting_links: List[str] = classification["meeting_links"]
        test_links: List[str] = classification["test_links"]

        text = (
            f"*{badge}*\n\n"
            f"📬 *Account:* `{account}`\n"
            f"👤 *From:* {sender}\n"
            f"📌 *Subject:* {subject}\n"
            f"📅 *Date:* {date_str}\n"
            f"🏷️ *Category:* `{category}`\n\n"
            f"💬 *Summary Excerpt:*\n_{snippet}_\n"
        )

        if meeting_links:
            text += "\n🗓️ *Meeting Links:*\n"
            for link in meeting_links[:2]:
                text += f"• [Join Meeting / Schedule]({link})\n"

        if test_links:
            text += "\n💻 *Test Links:*\n"
            for link in test_links[:2]:
                text += f"• [Open Assessment Portal]({link})\n"

        text += "\n⚡ *Action:* Check your inbox promptly."
        return text
