"""Google Calendar service — Phase 4.

Reuses the Gmail OAuth pattern; tokens live in email_credentials with
provider="gcal". Sync google-api-python-client wrapped in asyncio.to_thread.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

GCAL_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]
GCAL_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GCAL_TOKEN_URL = "https://oauth2.googleapis.com/token"


@dataclass
class CalendarEvent:
    id: str
    title: str
    start: datetime
    end: datetime
    attendees: list[str] = field(default_factory=list)
    location: str | None = None
    link: str | None = None


def _parse_gcal_dt(value: dict) -> datetime:
    raw = value.get("dateTime") or value.get("date")
    dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class GoogleCalendarService:
    """Same token-refresh contract as the email providers: after calls,
    check token_refreshed and persist new tokens."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        access_token: str,
        refresh_token: str,
        token_expiry: datetime | None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._token_expiry = token_expiry
        self.token_refreshed = False
        self.new_access_token: str | None = None
        self.new_refresh_token: str | None = None
        self.new_token_expiry: datetime | None = None

    def _build_service(self) -> Any:
        import google.auth.transport.requests
        import google.oauth2.credentials
        from googleapiclient.discovery import build

        creds = google.oauth2.credentials.Credentials(
            token=self._access_token,
            refresh_token=self._refresh_token,
            token_uri=GCAL_TOKEN_URL,
            client_id=self._client_id,
            client_secret=self._client_secret,
            scopes=GCAL_SCOPES,
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(google.auth.transport.requests.Request())
            self.token_refreshed = True
            self.new_access_token = creds.token
            self.new_token_expiry = creds.expiry
            self._access_token = creds.token
        return build("calendar", "v3", credentials=creds)

    @staticmethod
    def _parse_event(raw: dict) -> CalendarEvent:
        return CalendarEvent(
            id=raw["id"],
            title=raw.get("summary", "(no title)"),
            start=_parse_gcal_dt(raw.get("start", {})),
            end=_parse_gcal_dt(raw.get("end", {})),
            attendees=[
                a.get("email", "") for a in raw.get("attendees", []) if a.get("email")
            ],
            location=raw.get("location"),
            link=raw.get("htmlLink"),
        )

    async def list_events(
        self, time_min: datetime, time_max: datetime, limit: int = 20
    ) -> list[CalendarEvent]:
        def _sync() -> list[CalendarEvent]:
            service = self._build_service()
            result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min.isoformat(),
                    timeMax=time_max.isoformat(),
                    maxResults=limit,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            return [self._parse_event(e) for e in result.get("items", [])]

        return await asyncio.to_thread(_sync)

    async def create_event(
        self,
        title: str,
        start: datetime,
        end: datetime,
        attendees: list[str] | None = None,
        location: str | None = None,
        description: str | None = None,
    ) -> CalendarEvent:
        def _sync() -> CalendarEvent:
            service = self._build_service()
            body: dict[str, Any] = {
                "summary": title,
                "start": {"dateTime": start.isoformat()},
                "end": {"dateTime": end.isoformat()},
            }
            if attendees:
                body["attendees"] = [{"email": a} for a in attendees]
            if location:
                body["location"] = location
            if description:
                body["description"] = description
            raw = (
                service.events()
                .insert(calendarId="primary", body=body, sendUpdates="all")
                .execute()
            )
            return self._parse_event(raw)

        return await asyncio.to_thread(_sync)
