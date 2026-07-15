"""Scheduling Agent — Phase 4 full implementation.

Natural-language calendar over Google Calendar. Same LLM-parse →
structured-command pattern as the Email and Task agents.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.db.email_credential import EmailCredential
from app.services import audit
from app.services.gcal import CalendarEvent, GoogleCalendarService

logger = get_logger(__name__)

_PARSE_CALENDAR_CMD = """Parse this WhatsApp message into a calendar command.
Today's date/time (UTC): {now}
Reply with ONLY valid JSON, no markdown fences.

Message: "{message}"

JSON schema:
{{
  "action": "schedule" | "query" | "unknown",
  "title": "<event title, null unless scheduling>",
  "start": "<ISO 8601 datetime resolved from phrases like 'tomorrow 3pm', null if not given>",
  "duration_minutes": <integer, default 60 if scheduling and not stated>,
  "attendees": ["<email addresses mentioned, empty list if none>"],
  "location": "<location if mentioned, else null>",
  "query_date": "<ISO 8601 date for agenda queries like 'today'/'next Monday', null otherwise>"
}}"""


class SchedulingAgent:
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
        service, cred = await self._get_service_and_credential(db, user_id)
        if service is None:
            backend_url = self._settings.BACKEND_URL
            return (
                "📅 *Calendar not connected yet.*\n\n"
                f"Connect Google Calendar: `{backend_url}/api/v1/calendar/auth/google`\n"
                "Open the link in a browser while logged in to authorise access."
            )

        try:
            parsed = await self._parse_command(message)
            action = parsed.get("action")
            if action == "schedule" or intent == "calendar_schedule":
                result = await self._do_schedule(db, user_id, service, parsed)
            else:
                result = await self._do_query(db, user_id, service, parsed)
        except Exception as exc:
            logger.error("scheduling_agent_error", intent=intent, error=str(exc))
            await audit.log_action(
                db, action="calendar.error", user_id=user_id,
                status="error", details={"error": str(exc)},
            )
            return f"⚠️ Calendar error: {exc!s}"
        finally:
            await self._sync_tokens(db, cred, service)

        return result

    # ── schedule ──────────────────────────────────────────────────────────────

    async def _do_schedule(
        self, db: AsyncSession, user_id: uuid.UUID, service: GoogleCalendarService, parsed: dict
    ) -> str:
        title = (parsed.get("title") or "").strip()
        start = self._parse_iso(parsed.get("start"))
        if not title or not start:
            return (
                "📅 To schedule I need at least a title and a time.\n"
                "Try: 'schedule meeting with John tomorrow at 3pm'"
            )

        duration = int(parsed.get("duration_minutes") or 60)
        end = start + timedelta(minutes=duration)
        attendees = [a for a in (parsed.get("attendees") or []) if "@" in str(a)]

        # Conflict detection
        existing = await service.list_events(start, end, limit=5)
        conflict_note = ""
        if existing:
            names = ", ".join(e.title for e in existing[:3])
            conflict_note = f"\n⚠️ _Heads up — overlaps with: {names}_"

        event = await service.create_event(
            title=title, start=start, end=end,
            attendees=attendees, location=parsed.get("location"),
        )
        await audit.log_action(
            db, action="calendar.schedule", user_id=user_id,
            resource_type="calendar_event", resource_id=event.id,
            details={"title": title, "start": start.isoformat()},
        )

        lines = [
            f"📅 *Scheduled:* {event.title}",
            f"🕐 {event.start.strftime('%a %b %d, %H:%M')} – {event.end.strftime('%H:%M')} UTC",
        ]
        if attendees:
            lines.append(f"👥 Invited: {', '.join(attendees)}")
        if event.location:
            lines.append(f"📍 {event.location}")
        return "\n".join(lines) + conflict_note

    # ── query ─────────────────────────────────────────────────────────────────

    async def _do_query(
        self, db: AsyncSession, user_id: uuid.UUID, service: GoogleCalendarService, parsed: dict
    ) -> str:
        query_date = self._parse_iso(parsed.get("query_date"))
        day_start = (query_date or datetime.now(timezone.utc)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        day_end = day_start + timedelta(days=1)

        events = await service.list_events(day_start, day_end, limit=15)
        await audit.log_action(
            db, action="calendar.query", user_id=user_id,
            details={"date": day_start.date().isoformat(), "events": len(events)},
        )

        label = day_start.strftime("%A %b %d")
        if not events:
            return f"📅 *{label}:* No events. Your calendar is clear! 🎉"

        lines = [f"📅 *{label} — {len(events)} event{'s' if len(events) != 1 else ''}*"]
        for e in events:
            att = f" ({len(e.attendees)} attendees)" if e.attendees else ""
            loc = f" @ {e.location}" if e.location else ""
            lines.append(
                f"• {e.start.strftime('%H:%M')}–{e.end.strftime('%H:%M')} {e.title}{loc}{att}"
            )
        return "\n".join(lines)

    # ── helpers ───────────────────────────────────────────────────────────────

    async def _get_service_and_credential(
        self, db: AsyncSession, user_id: uuid.UUID
    ) -> tuple[GoogleCalendarService | None, EmailCredential | None]:
        from app.agents.email_agent import decrypt_token

        result = await db.execute(
            select(EmailCredential).where(
                EmailCredential.user_id == user_id,
                EmailCredential.provider == "gcal",
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
            logger.error("gcal_token_decrypt_failed", user_id=str(user_id))
            return None, None

        service = GoogleCalendarService(
            client_id=self._settings.GMAIL_CLIENT_ID or "",
            client_secret=self._settings.GMAIL_CLIENT_SECRET or "",
            access_token=access_token,
            refresh_token=refresh_token,
            token_expiry=cred.token_expiry,
        )
        return service, cred

    async def _sync_tokens(
        self, db: AsyncSession, cred, service: GoogleCalendarService | None
    ) -> None:
        from app.agents.email_agent import encrypt_token

        if cred is None or service is None or not service.token_refreshed:
            return
        if service.new_access_token:
            cred.access_token_enc = encrypt_token(service.new_access_token)
        if service.new_refresh_token:
            cred.refresh_token_enc = encrypt_token(service.new_refresh_token)
        if service.new_token_expiry:
            cred.token_expiry = service.new_token_expiry
        cred.updated_at = datetime.now(timezone.utc)
        await db.commit()

    async def _parse_command(self, message: str) -> dict:
        try:
            result = await self._ollama.chat(
                messages=[
                    {
                        "role": "user",
                        "content": _PARSE_CALENDAR_CMD.format(
                            message=message,
                            now=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M %A"),
                        ),
                    }
                ],
                model=self._settings.OLLAMA_FAST_MODEL,
                temperature=0.0,
                max_tokens=250,
            )
            raw = result["content"].strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw)
        except Exception as exc:
            logger.warning("calendar_parse_failed", error=str(exc))
            return {}

    @staticmethod
    def _parse_iso(value) -> datetime | None:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None
