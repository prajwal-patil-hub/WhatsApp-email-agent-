"""Scheduling Agent — Phase 4. Stub with interface defined."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class CalendarEvent:
    id: str
    title: str
    start: datetime
    end: datetime
    attendees: list[str]
    location: str | None


class SchedulingAgent:
    """
    Phase 4 implementation will include:
    - Google Calendar OAuth2 integration
    - Outlook Calendar integration
    - Natural language scheduling ("schedule with John tomorrow at 3pm")
    - Conflict detection
    - Meeting preparation briefs
    - Agenda generation
    - Smart scheduling suggestions based on preferences
    """

    async def schedule_meeting(
        self, user_id: str, description: str
    ) -> CalendarEvent:
        raise NotImplementedError("Scheduling Agent available in Phase 4")

    async def get_agenda(self, user_id: str, date: str) -> list[CalendarEvent]:
        raise NotImplementedError("Scheduling Agent available in Phase 4")

    async def find_slot(
        self, user_id: str, duration_minutes: int, attendees: list[str]
    ) -> list[datetime]:
        raise NotImplementedError("Scheduling Agent available in Phase 4")
