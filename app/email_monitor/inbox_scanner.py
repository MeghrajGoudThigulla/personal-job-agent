"""
Inbox Scanner: Gmail & Outlook IMAP client.
Connects via IMAP SSL with App Passwords, scans for hiring updates,
classifies emails, and triggers immediate Telegram notifications.
"""

from __future__ import annotations

import asyncio
import email
from email.header import decode_header
import imaplib
import logging
import re
from typing import Any, Dict, List, Optional
from sqlalchemy import select

from app.config import settings
from app.core.database import async_session_factory
from app.core.models import SeenEmail
from app.email_monitor.summarizer import EmailSummarizer
from app.notifiers.telegram import TelegramNotifier

logger = logging.getLogger("personal_job_agent.email_monitor")


def decode_mime_header(header_value: str) -> str:
    """Decodes MIME encoded email header fields."""
    if not header_value:
        return ""
    decoded_fragments = decode_header(header_value)
    result = []
    for fragment, charset in decoded_fragments:
        if isinstance(fragment, bytes):
            try:
                result.append(fragment.decode(charset or "utf-8", errors="replace"))
            except Exception:
                result.append(fragment.decode("utf-8", errors="replace"))
        else:
            result.append(str(fragment))
    return " ".join(result)


def extract_body(msg: email.message.Message) -> str:
    """Extracts plain text or stripped HTML from email message payload."""
    body_text = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in content_disposition:
                continue
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
            elif content_type == "text/html" and not body_text:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html_content = payload.decode(charset, errors="replace")
                    body_text = re.sub(r"<[^>]+>", " ", html_content)
    else:
        content_type = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            raw = payload.decode(charset, errors="replace")
            if content_type == "text/html":
                return re.sub(r"<[^>]+>", " ", raw)
            return raw

    return body_text


class InboxScanner:
    """
    Connects to Gmail & Outlook to read and alert on recruitment emails.
    """

    def __init__(self, notifier: Optional[TelegramNotifier] = None):
        self.notifier = notifier or TelegramNotifier()

    def _scan_imap_sync(
        self,
        account_name: str,
        host: str,
        port: int,
        user: str,
        app_password: str,
        seen_ids: set[str],
    ) -> List[Dict[str, Any]]:
        """
        Synchronous worker running in a thread: logs into IMAP SSL,
        scans recent unread/search results, extracts candidate emails.
        """
        if not user or not app_password:
            return []

        found_emails = []
        try:
            mail = imaplib.IMAP4_SSL(host, port)
            mail.login(user, app_password)
            mail.select("INBOX", readonly=True)

            # Search unread messages from past 48 hours
            status, response = mail.search(None, "UNSEEN")
            if status != "OK" or not response or not response[0]:
                # Fallback: search last 10 messages
                status, response = mail.search(None, "ALL")

            if status == "OK" and response and response[0]:
                msg_ids = response[0].split()
                # Scan newest 15 messages max
                recent_ids = msg_ids[-15:]

                for mid in reversed(recent_ids):
                    res, data = mail.fetch(mid, "(RFC822)")
                    if res != "OK" or not data or not data[0]:
                        continue

                    raw_email = data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    message_id = (msg.get("Message-ID") or f"{account_name}_{mid.decode('ascii', errors='ignore')}").strip("<>")
                    if message_id in seen_ids:
                        continue

                    subject = decode_mime_header(msg.get("Subject", "No Subject"))
                    sender = decode_mime_header(msg.get("From", "Unknown Sender"))
                    date_str = msg.get("Date", "")
                    body = extract_body(msg)

                    # Quick filter: is this email recruiting/job related?
                    combined = f"{subject}\n{body}".lower()
                    hiring_terms = [
                        "interview", "invitation", "assessment", "hackerrank", "codility",
                        "codesignal", "offer", "regret to inform", "application", "shortlist",
                        "candidate", "screening", "next steps", "talent", "recruiting"
                    ]
                    if not any(term in combined for term in hiring_terms):
                        continue

                    classification = EmailSummarizer.classify(subject, body)
                    found_emails.append({
                        "message_id": message_id,
                        "account": account_name,
                        "sender": sender,
                        "subject": subject,
                        "date": date_str,
                        "body": body,
                        "classification": classification,
                    })

            mail.logout()
        except Exception as e:
            logger.warning(f"IMAP scan failed for {account_name} ({user}): {e}")

        return found_emails

    async def scan_all_accounts(self) -> Dict[str, Any]:
        """
        Scans both Gmail and Outlook, checks SeenEmail table,
        and fires immediate Telegram alerts for newly discovered hiring emails.
        """
        # 1. Fetch already seen message IDs from DB
        seen_ids = set()
        async with async_session_factory() as session:
            rows = await session.execute(select(SeenEmail.message_id))
            seen_ids = set(rows.scalars().all())

        new_emails: List[Dict[str, Any]] = []

        # 2. Scan Gmail
        if settings.GMAIL_USER and settings.GMAIL_APP_PASSWORD:
            gmail_found = await asyncio.to_thread(
                self._scan_imap_sync,
                "Gmail",
                settings.GMAIL_IMAP_HOST,
                settings.GMAIL_IMAP_PORT,
                settings.GMAIL_USER,
                settings.GMAIL_APP_PASSWORD,
                seen_ids,
            )
            new_emails.extend(gmail_found)

        # 3. Scan Outlook
        if settings.OUTLOOK_USER and settings.OUTLOOK_APP_PASSWORD:
            outlook_found = await asyncio.to_thread(
                self._scan_imap_sync,
                "Outlook",
                settings.OUTLOOK_IMAP_HOST,
                settings.OUTLOOK_IMAP_PORT,
                settings.OUTLOOK_USER,
                settings.OUTLOOK_APP_PASSWORD,
                seen_ids,
            )
            new_emails.extend(outlook_found)

        # 4. Notify and save to DB
        notified_count = 0
        async with async_session_factory() as session:
            for item in new_emails:
                mid = item["message_id"]
                if mid in seen_ids:
                    continue

                account = item["account"]
                sender = item["sender"]
                subject = item["subject"]
                date_str = item["date"]
                classification = item["classification"]

                # Fire Telegram alert immediately
                if self.notifier.is_configured:
                    alert_text = EmailSummarizer.format_telegram_alert(
                        account=account,
                        sender=sender,
                        subject=subject,
                        date_str=date_str,
                        classification=classification,
                    )
                    sent = await self.notifier.send_message(alert_text)
                    if sent:
                        notified_count += 1

                # Record seen email in DB
                seen_rec = SeenEmail(
                    message_id=mid,
                    account=account,
                    subject=subject[:500],
                    category=classification["category"][:100],
                )
                session.add(seen_rec)
                seen_ids.add(mid)

            await session.commit()

        summary = {
            "status": "success",
            "scanned_accounts": [
                account for account, enabled in [
                    ("Gmail", bool(settings.GMAIL_USER and settings.GMAIL_APP_PASSWORD)),
                    ("Outlook", bool(settings.OUTLOOK_USER and settings.OUTLOOK_APP_PASSWORD)),
                ] if enabled
            ],
            "new_emails_found": len(new_emails),
            "notified_count": notified_count,
        }
        logger.info(f"Email scan finished: {summary}")
        return summary
