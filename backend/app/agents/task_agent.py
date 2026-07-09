"""Task Agent — Phase 3 full implementation.

Natural-language task management over the tasks table. The LLM parses
WhatsApp messages into structured commands; all persistence is plain
SQLAlchemy. Completing a recurring task spawns the next occurrence.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.db.task import Task
from app.services import audit

logger = get_logger(__name__)

VALID_PRIORITIES = ("urgent", "high", "medium", "low")
VALID_RECURRENCES = ("daily", "weekly", "monthly")

_PRIORITY_EMOJI = {"urgent": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}

_RECURRENCE_DELTAS = {
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
    "monthly": timedelta(days=30),
}


@dataclass
class TaskResult:
    id: str
    title: str
    priority: str
    status: str
    due_date: datetime | None


_PARSE_TASK_CMD = """Parse this WhatsApp message into a task command.
Today's date/time (UTC): {now}
Reply with ONLY valid JSON, no markdown fences.

Message: "{message}"

JSON schema:
{{
  "action": "create" | "list" | "complete" | "update" | "delete" | "unknown",
  "title": "<task title, null unless creating>",
  "priority": "urgent" | "high" | "medium" | "low" | null,
  "due_date": "<ISO 8601 datetime resolved from phrases like 'tomorrow 5pm' or 'next Friday', null if none>",
  "project": "<project name if mentioned, else null>",
  "recurrence": "daily" | "weekly" | "monthly" | null,
  "task_ref": "<number or keywords identifying an existing task, e.g. '2' or 'dentist', null>",
  "status_filter": "pending" | "completed" | "all" | null,
  "new_status": "<for updates: pending | in_progress | completed | cancelled, else null>"
}}

Priority hints: "ASAP"/"urgent"/"critical" → urgent; "important" → high; "sometime"/"whenever" → low; default medium."""


class TaskAgent:
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
        try:
            parsed = await self._parse_command(message)
            action = parsed.get("action") or {
                "task_create": "create",
                "task_list": "list",
                "task_update": "update",
            }.get(intent, "unknown")

            if action == "create" or intent == "task_create":
                return await self._do_create(db, user_id, parsed, message)
            if action == "list" or intent == "task_list":
                return await self._do_list(db, user_id, parsed)
            if action == "complete":
                return await self._do_complete(db, user_id, parsed)
            if action in ("update", "delete"):
                return await self._do_update(db, user_id, parsed, action)
            return (
                "I can create, list, update, or complete tasks. "
                "Try 'add task: call dentist tomorrow 3pm' or 'show my tasks'."
            )
        except Exception as exc:
            logger.error("task_agent_error", intent=intent, error=str(exc))
            await audit.log_action(
                db,
                action="task.error",
                user_id=user_id,
                status="error",
                details={"error": str(exc)},
            )
            return f"⚠️ Task error: {exc!s}"

    # ── create ────────────────────────────────────────────────────────────────

    async def _do_create(
        self, db: AsyncSession, user_id: uuid.UUID, parsed: dict, message: str
    ) -> str:
        title = (parsed.get("title") or "").strip()
        if not title:
            title = message.strip()[:500]

        priority = parsed.get("priority") or "medium"
        if priority not in VALID_PRIORITIES:
            priority = "medium"

        recurrence = parsed.get("recurrence")
        if recurrence not in VALID_RECURRENCES:
            recurrence = None

        due_date = self._parse_iso(parsed.get("due_date"))

        task = Task(
            user_id=user_id,
            title=title,
            priority=priority,
            due_date=due_date,
            project=parsed.get("project"),
            recurrence=recurrence,
            source_channel="whatsapp",
        )
        db.add(task)
        await db.flush()
        await audit.log_action(
            db,
            action="task.create",
            user_id=user_id,
            resource_type="task",
            resource_id=str(task.id),
            details={"title": title, "priority": priority},
        )

        lines = [f"✅ *Task created:* {title}"]
        lines.append(f"{_PRIORITY_EMOJI[priority]} Priority: {priority}")
        if due_date:
            lines.append(f"📅 Due: {due_date.strftime('%a %b %d, %H:%M')}")
        if recurrence:
            lines.append(f"🔁 Repeats: {recurrence}")
        if parsed.get("project"):
            lines.append(f"📁 Project: {parsed['project']}")
        return "\n".join(lines)

    # ── list ──────────────────────────────────────────────────────────────────

    async def _do_list(self, db: AsyncSession, user_id: uuid.UUID, parsed: dict) -> str:
        status_filter = parsed.get("status_filter") or "pending"
        query = select(Task).where(Task.user_id == user_id)
        if status_filter != "all":
            query = query.where(Task.status == status_filter)
        query = query.order_by(Task.due_date.asc().nulls_last(), Task.created_at.asc()).limit(15)

        result = await db.execute(query)
        tasks = list(result.scalars().all())

        await audit.log_action(
            db, action="task.list", user_id=user_id, details={"count": len(tasks)}
        )

        if not tasks:
            return "📋 No tasks found. Add one with 'add task: ...'"

        now = datetime.now(timezone.utc)
        lines = [f"📋 *Your tasks ({len(tasks)})*"]
        for i, t in enumerate(tasks, 1):
            due = ""
            if t.due_date:
                due_dt = t.due_date if t.due_date.tzinfo else t.due_date.replace(tzinfo=timezone.utc)
                overdue = " ⚠️ OVERDUE" if due_dt < now and t.status == "pending" else ""
                due = f" — due {due_dt.strftime('%b %d %H:%M')}{overdue}"
            rec = " 🔁" if t.recurrence else ""
            lines.append(f"{i}. {_PRIORITY_EMOJI.get(t.priority, '⚪')} {t.title}{due}{rec}")
        lines.append("\n_Say 'complete task N' to mark one done._")
        return "\n".join(lines)

    # ── complete ──────────────────────────────────────────────────────────────

    async def _do_complete(self, db: AsyncSession, user_id: uuid.UUID, parsed: dict) -> str:
        task = await self._find_task(db, user_id, parsed.get("task_ref"))
        if task is None:
            return "🤔 I couldn't find that task. Say 'show my tasks' to see the numbered list."

        now = datetime.now(timezone.utc)
        task.status = "completed"
        task.completed_at = now

        next_task_msg = ""
        if task.recurrence in _RECURRENCE_DELTAS:
            base = task.due_date or now
            if base.tzinfo is None:
                base = base.replace(tzinfo=timezone.utc)
            next_due = base + _RECURRENCE_DELTAS[task.recurrence]
            while next_due < now:
                next_due += _RECURRENCE_DELTAS[task.recurrence]
            db.add(
                Task(
                    user_id=user_id,
                    title=task.title,
                    description=task.description,
                    priority=task.priority,
                    due_date=next_due,
                    project=task.project,
                    recurrence=task.recurrence,
                    source_channel="recurrence",
                )
            )
            next_task_msg = f"\n🔁 Next occurrence scheduled: {next_due.strftime('%a %b %d')}"

        await db.flush()
        await audit.log_action(
            db,
            action="task.complete",
            user_id=user_id,
            resource_type="task",
            resource_id=str(task.id),
        )
        return f"🎉 *Done:* {task.title}{next_task_msg}"

    # ── update / delete ───────────────────────────────────────────────────────

    async def _do_update(
        self, db: AsyncSession, user_id: uuid.UUID, parsed: dict, action: str
    ) -> str:
        task = await self._find_task(db, user_id, parsed.get("task_ref"))
        if task is None:
            return "🤔 I couldn't find that task. Say 'show my tasks' to see the numbered list."

        if action == "delete":
            task.status = "cancelled"
            await db.flush()
            await audit.log_action(
                db, action="task.cancel", user_id=user_id,
                resource_type="task", resource_id=str(task.id),
            )
            return f"🗑️ Cancelled: {task.title}"

        changes = []
        if parsed.get("priority") in VALID_PRIORITIES:
            task.priority = parsed["priority"]
            changes.append(f"priority → {task.priority}")
        new_due = self._parse_iso(parsed.get("due_date"))
        if new_due:
            task.due_date = new_due
            changes.append(f"due → {new_due.strftime('%b %d %H:%M')}")
        if parsed.get("new_status") in ("pending", "in_progress", "completed", "cancelled"):
            task.status = parsed["new_status"]
            if task.status == "completed":
                task.completed_at = datetime.now(timezone.utc)
            changes.append(f"status → {task.status}")
        if parsed.get("project"):
            task.project = parsed["project"]
            changes.append(f"project → {task.project}")

        if not changes:
            return f"ℹ️ Nothing to change on: {task.title}"

        await db.flush()
        await audit.log_action(
            db, action="task.update", user_id=user_id,
            resource_type="task", resource_id=str(task.id),
            details={"changes": changes},
        )
        return f"✏️ *Updated:* {task.title}\n" + "\n".join(f"  • {c}" for c in changes)

    # ── helpers ───────────────────────────────────────────────────────────────

    async def _find_task(
        self, db: AsyncSession, user_id: uuid.UUID, task_ref
    ) -> Task | None:
        """Resolve a task by list position (as shown by _do_list) or title keyword."""
        result = await db.execute(
            select(Task)
            .where(Task.user_id == user_id, Task.status == "pending")
            .order_by(Task.due_date.asc().nulls_last(), Task.created_at.asc())
            .limit(15)
        )
        tasks = list(result.scalars().all())
        if not tasks or task_ref is None:
            return None

        ref = str(task_ref).strip().lower()
        if ref.lstrip("#").isdigit():
            idx = int(ref.lstrip("#"))
            if 1 <= idx <= len(tasks):
                return tasks[idx - 1]
            return None

        matches = [t for t in tasks if ref in t.title.lower()]
        return matches[0] if len(matches) >= 1 else None

    async def _parse_command(self, message: str) -> dict:
        try:
            result = await self._ollama.chat(
                messages=[
                    {
                        "role": "user",
                        "content": _PARSE_TASK_CMD.format(
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
            logger.warning("task_parse_failed", error=str(exc))
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
