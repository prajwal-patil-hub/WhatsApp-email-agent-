"""Task Agent — Phase 3. Stub with interface defined."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class TaskResult:
    id: str
    title: str
    priority: str
    status: str
    due_date: datetime | None


class TaskAgent:
    """
    Phase 3 implementation will include:
    - Natural language task creation
    - Priority inference from message context
    - Recurring task engine
    - Due date reminders via WhatsApp
    - Project grouping
    - Proactive overdue nudges
    """

    async def create_from_message(self, user_id: str, message: str) -> TaskResult:
        raise NotImplementedError("Task Agent available in Phase 3")

    async def list_tasks(
        self, user_id: str, status: str | None = None, priority: str | None = None
    ) -> list[TaskResult]:
        raise NotImplementedError("Task Agent available in Phase 3")

    async def complete_task(self, user_id: str, task_id: str) -> TaskResult:
        raise NotImplementedError("Task Agent available in Phase 3")
