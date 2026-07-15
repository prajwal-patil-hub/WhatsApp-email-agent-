"""Executive briefing service — Phase 7.

Aggregates tasks, calendar, and goals into a single WhatsApp-ready
briefing. Each data source degrades independently — a dead integration
never kills the briefing.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.db.task import Task

logger = get_logger(__name__)

_PRIORITY_EMOJI = {"urgent": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}


async def build_briefing(db: AsyncSession, user_id: uuid.UUID, ollama=None) -> str:
    now = datetime.now(timezone.utc)
    lines = [f"🌅 *Executive Briefing*\n_{now.strftime('%A, %B %d, %Y')}_\n"]

    lines.append(await _tasks_section(db, user_id, now))
    lines.append(await _calendar_section(db, user_id, now))
    lines.append(await _goals_section(db, user_id))
    lines.append("_Reply 'show my tasks' or ask me anything._")
    return "\n".join(part for part in lines if part)


async def _tasks_section(db: AsyncSession, user_id: uuid.UUID, now: datetime) -> str:
    try:
        result = await db.execute(
            select(Task)
            .where(Task.user_id == user_id, Task.status == "pending")
            .order_by(Task.due_date.asc().nulls_last(), Task.created_at.asc())
            .limit(10)
        )
        tasks = list(result.scalars().all())
    except Exception as exc:
        logger.warning("briefing_tasks_failed", error=str(exc))
        return ""

    if not tasks:
        return "✅ *Tasks:* Nothing pending. Clear runway! 🎉\n"

    overdue, today_due, other = [], [], []
    for t in tasks:
        if t.due_date:
            due = t.due_date if t.due_date.tzinfo else t.due_date.replace(tzinfo=timezone.utc)
            if due < now:
                overdue.append(t)
            elif due.date() == now.date():
                today_due.append(t)
            else:
                other.append(t)
        else:
            other.append(t)

    lines = [f"✅ *Tasks ({len(tasks)} pending)*"]
    for label, bucket in (("⚠️ Overdue", overdue), ("📌 Due today", today_due)):
        for t in bucket[:3]:
            lines.append(f"{label}: {_PRIORITY_EMOJI.get(t.priority, '⚪')} {t.title}")
    for t in other[:3]:
        lines.append(f"• {_PRIORITY_EMOJI.get(t.priority, '⚪')} {t.title}")
    return "\n".join(lines) + "\n"


async def _calendar_section(db: AsyncSession, user_id: uuid.UUID, now: datetime) -> str:
    try:
        from app.agents.scheduling_agent import SchedulingAgent

        agent = SchedulingAgent(ollama=None)
        service, cred = await agent._get_service_and_credential(db, user_id)
        if service is None:
            return ""
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        events = await service.list_events(now, day_start + timedelta(days=1), limit=8)
        await agent._sync_tokens(db, cred, service)
    except Exception as exc:
        logger.warning("briefing_calendar_failed", error=str(exc))
        return ""

    if not events:
        return "📅 *Calendar:* No more events today.\n"
    lines = [f"📅 *Today ({len(events)} remaining)*"]
    for e in events:
        lines.append(f"• {e.start.strftime('%H:%M')} {e.title}")
    return "\n".join(lines) + "\n"


async def _goals_section(db: AsyncSession, user_id: uuid.UUID) -> str:
    try:
        from app.memory.long_term import search_memories

        goals = await search_memories(db, user_id, memory_type="goal", limit=3)
    except Exception as exc:
        logger.warning("briefing_goals_failed", error=str(exc))
        return ""

    if not goals:
        return ""
    lines = ["🎯 *Active Goals*"]
    for g in goals:
        lines.append(f"• {g.summary or g.content[:80]}")
    return "\n".join(lines) + "\n"
