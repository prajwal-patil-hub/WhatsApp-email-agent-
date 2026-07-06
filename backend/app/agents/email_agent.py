"""Email Agent — Phase 2 full implementation.

Handles Gmail and Outlook via a provider abstraction. Tokens are stored
encrypted in the email_credentials table and refreshed transparently.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.db.email_credential import EmailCredential
from app.services import audit
from app.services.email_provider import EmailProvider

logger = get_logger(__name__)


# ── Token encryption ──────────────────────────────────────────────────────────

def _fernet():
    import base64
    import hashlib

    from cryptography.fernet import Fernet

    raw = hashlib.sha256(get_settings().SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(raw))


def encrypt_token(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()


# ── Backwards-compat dataclasses (used by route layer) ───────────────────────

@dataclass
class EmailSummary:
    subject: str
    sender: str
    preview: str
    priority: str
    received_at: str


@dataclass
class DraftedEmail:
    to: str
    subject: str
    body: str
    thread_id: str | None = None


# ── LLM prompts ───────────────────────────────────────────────────────────────

_PARSE_EMAIL_CMD = """Parse this WhatsApp message into an email command.
Reply with ONLY valid JSON, no markdown fences.

Message: "{message}"

JSON schema:
{{
  "action": "read" | "draft" | "send" | "unknown",
  "recipient": "<email address or name, null if not provided>",
  "subject": "<email subject, null if not provided>",
  "content": "<what the email should say>",
  "email_ref": "<reference to a numbered email, e.g. '#2' or null>"
}}"""

_SUMMARIZE_EMAILS = """Summarize these emails for a WhatsApp message. Be concise.
For each email: sender, subject, one-sentence gist, and urgency (🔴 urgent / 🟡 normal / 🟢 low).
Numbered list. Max 3 sentences per email.

Emails:
{emails}"""

_DRAFT_REPLY = """You are drafting a professional email reply.

Original thread:
{thread}

User instructions: {instructions}

Write ONLY the email body. No subject line. No salutation header.
Professional, concise, match the tone of the thread."""


class EmailAgent:
    def __init__(self, ollama) -> None:
        self._ollama = ollama
        self._settings = get_settings()

    # ── Coordinator entry point ───────────────────────────────────────────────

    async def handle_command(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        intent: str,
        message: str,
    ) -> str:
        provider, cred = await self._get_provider_and_credential(db, user_id)
        if provider is None:
            return self._not_connected_message()

        try:
            if intent == "email_read":
                result = await self._do_read(db, user_id, provider)
            elif intent == "email_draft":
                result = await self._do_draft(db, user_id, provider, message)
            elif intent == "email_send":
                result = await self._do_send(db, user_id, provider, message)
            else:
                result = (
                    "I'm not sure what you'd like to do with your email. "
                    "Try 'check my emails' or 'send email to someone@example.com'."
                )
        except Exception as exc:
            logger.error("email_agent_error", intent=intent, error=str(exc))
            await audit.log_action(
                db,
                action=f"email.{intent}.error",
                user_id=user_id,
                status="error",
                details={"error": str(exc)},
            )
            return (
                f"⚠️ Email error: {exc!s}\n"
                "If this keeps happening, try reconnecting your email via the dashboard."
            )
        finally:
            await self._sync_tokens(db, cred, provider)

        return result

    # ── email_read ────────────────────────────────────────────────────────────

    async def _do_read(
        self, db: AsyncSession, user_id: uuid.UUID, provider: EmailProvider
    ) -> str:
        messages = await provider.get_unread(limit=10)
        await audit.log_action(
            db,
            action="email.read",
            user_id=user_id,
            details={"unread_count": len(messages)},
        )
        if not messages:
            return "📭 *Inbox clear!* No unread emails right now."

        email_text = "\n\n".join(
            f"Email {i + 1}:\n"
            f"From: {m.sender} <{m.sender_email}>\n"
            f"Subject: {m.subject}\n"
            f"Date: {m.received_at.strftime('%b %d %H:%M')}\n"
            f"Preview: {m.snippet}"
            for i, m in enumerate(messages[:10])
        )
        result = await self._ollama.chat(
            messages=[{"role": "user", "content": _SUMMARIZE_EMAILS.format(emails=email_text)}],
            model=self._settings.OLLAMA_DEFAULT_MODEL,
            temperature=0.3,
        )
        summary = result["content"].strip()
        return f"📧 *Unread Emails ({len(messages)})*\n\n{summary}"

    # ── email_draft ───────────────────────────────────────────────────────────

    async def _do_draft(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        provider: EmailProvider,
        message: str,
    ) -> str:
        parsed = await self._parse_command(message)
        instructions = parsed.get("content") or message
        thread_text = ""
        thread_id = None

        email_ref = parsed.get("email_ref")
        if email_ref:
            ref_num = self._extract_ref_number(email_ref)
            if ref_num is not None:
                unread = await provider.get_unread(limit=ref_num)
                if len(unread) >= ref_num:
                    target = unread[ref_num - 1]
                    thread_id = target.thread_id
                    thread = await provider.get_thread(target.thread_id)
                    thread_text = "\n---\n".join(
                        f"From: {m.sender_email}\nSubject: {m.subject}\n{m.body_text}"
                        for m in thread.messages[-3:]
                    )

        result = await self._ollama.chat(
            messages=[
                {
                    "role": "user",
                    "content": _DRAFT_REPLY.format(
                        thread=thread_text or "(new email — no prior thread)",
                        instructions=instructions,
                    ),
                }
            ],
            model=self._settings.OLLAMA_DEFAULT_MODEL,
            temperature=0.5,
        )
        draft_body = result["content"].strip()
        await audit.log_action(
            db, action="email.draft", user_id=user_id, details={"has_thread": bool(thread_id)}
        )
        recipient = parsed.get("recipient") or "(not specified)"
        subject = parsed.get("subject") or "(not specified)"
        return (
            f"✉️ *Draft ready*\n\n"
            f"*To:* {recipient}\n"
            f"*Subject:* {subject}\n\n"
            f"---\n{draft_body}\n---\n\n"
            f"Reply 'send it' to send, or give me revision instructions."
        )

    # ── email_send ────────────────────────────────────────────────────────────

    async def _do_send(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        provider: EmailProvider,
        message: str,
    ) -> str:
        parsed = await self._parse_command(message)
        recipient = parsed.get("recipient")
        subject = parsed.get("subject") or "Message from your AI Chief of Staff"
        body = parsed.get("content") or message

        if not recipient or "@" not in str(recipient):
            return (
                "📧 To send an email I need a valid email address.\n"
                "Try: 'send email to john@example.com — I'll be there at 3pm'"
            )

        await provider.send(to=recipient, subject=subject, body=body)
        await audit.log_action(
            db,
            action="email.send",
            user_id=user_id,
            details={"to": recipient, "subject": subject},
        )
        return f"✅ Email sent to *{recipient}*\nSubject: _{subject}_"

    # ── helpers ───────────────────────────────────────────────────────────────

    async def _parse_command(self, message: str) -> dict:
        try:
            result = await self._ollama.chat(
                messages=[
                    {"role": "user", "content": _PARSE_EMAIL_CMD.format(message=message)}
                ],
                model=self._settings.OLLAMA_FAST_MODEL,
                temperature=0.0,
                max_tokens=200,
            )
            raw = result["content"].strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw)
        except Exception as exc:
            logger.warning("email_parse_failed", error=str(exc))
            return {}

    @staticmethod
    def _extract_ref_number(ref: str) -> int | None:
        import re

        match = re.search(r"\d+", str(ref))
        return int(match.group()) if match else None

    async def _get_provider_and_credential(
        self, db: AsyncSession, user_id: uuid.UUID
    ) -> tuple[EmailProvider | None, EmailCredential | None]:
        result = await db.execute(
            select(EmailCredential).where(
                EmailCredential.user_id == user_id,
                EmailCredential.is_active.is_(True),
            )
        )
        cred = result.scalar_one_or_none()
        if cred is None:
            return None, None

        try:
            access_token = decrypt_token(cred.access_token_enc)
            refresh_token = (
                decrypt_token(cred.refresh_token_enc) if cred.refresh_token_enc else ""
            )
        except Exception:
            logger.error("email_token_decrypt_failed", user_id=str(user_id))
            return None, None

        provider: EmailProvider
        if cred.provider == "gmail":
            from app.services.gmail import GmailProvider

            provider = GmailProvider(
                client_id=self._settings.GMAIL_CLIENT_ID or "",
                client_secret=self._settings.GMAIL_CLIENT_SECRET or "",
                access_token=access_token,
                refresh_token=refresh_token,
                token_expiry=cred.token_expiry,
            )
        elif cred.provider == "outlook":
            from app.services.outlook import OutlookProvider

            provider = OutlookProvider(
                client_id=self._settings.OUTLOOK_CLIENT_ID or "",
                client_secret=self._settings.OUTLOOK_CLIENT_SECRET or "",
                tenant_id=self._settings.OUTLOOK_TENANT_ID,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expiry=cred.token_expiry,
            )
        else:
            logger.error("unknown_email_provider", provider=cred.provider)
            return None, None

        return provider, cred

    async def _sync_tokens(
        self,
        db: AsyncSession,
        cred: EmailCredential | None,
        provider: EmailProvider | None,
    ) -> None:
        if cred is None or provider is None or not provider.token_refreshed:
            return
        if provider.new_access_token:
            cred.access_token_enc = encrypt_token(provider.new_access_token)
        if provider.new_refresh_token:
            cred.refresh_token_enc = encrypt_token(provider.new_refresh_token)
        if provider.new_token_expiry:
            cred.token_expiry = provider.new_token_expiry
        cred.updated_at = datetime.now(timezone.utc)
        await db.commit()

    def _not_connected_message(self) -> str:
        backend_url = self._settings.BACKEND_URL
        return (
            "📧 *Email not connected yet.*\n\n"
            "Connect your email to get started:\n"
            f"• Gmail: `{backend_url}/api/v1/email/auth/gmail`\n"
            f"• Outlook: `{backend_url}/api/v1/email/auth/outlook`\n\n"
            "Open the link in a browser while logged in to authorise access."
        )
