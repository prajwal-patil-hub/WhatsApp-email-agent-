"""Google Calendar OAuth + event routes — Phase 4.

Token storage reuses email_credentials with provider="gcal".
OAuth state CSRF protection reuses the email routes' JWT state tokens.
"""

import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from app.agents.email_agent import encrypt_token
from app.api.deps import CurrentUser, Database
from app.api.routes.email import _decode_state_token, _make_state_token
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.db.email_credential import EmailCredential
from app.services import audit
from app.services.gcal import GCAL_AUTH_URL, GCAL_SCOPES, GCAL_TOKEN_URL

router = APIRouter(prefix="/calendar", tags=["calendar"])
logger = get_logger(__name__)


class CalendarStatusResponse(BaseModel):
    connected: bool
    email_address: str | None = None


class CalendarAuthUrlResponse(BaseModel):
    auth_url: str
    message: str


class EventCreateRequest(BaseModel):
    title: str
    start: datetime
    duration_minutes: int = 60
    attendees: list[str] = []
    location: str | None = None
    description: str | None = None


class EventResponse(BaseModel):
    id: str
    title: str
    start: datetime
    end: datetime
    attendees: list[str]
    location: str | None
    link: str | None


class EventListResponse(BaseModel):
    items: list[EventResponse]
    total: int


async def _get_gcal_service(db, user_id: uuid.UUID):
    from app.agents.scheduling_agent import SchedulingAgent

    agent = SchedulingAgent(ollama=None)
    return await agent._get_service_and_credential(db, user_id), agent


@router.get("/status", response_model=CalendarStatusResponse)
async def calendar_status(current_user: CurrentUser, db: Database) -> CalendarStatusResponse:
    result = await db.execute(
        select(EmailCredential).where(
            EmailCredential.user_id == current_user.id,
            EmailCredential.provider == "gcal",
            EmailCredential.is_active.is_(True),
        )
    )
    cred = result.scalar_one_or_none()
    return CalendarStatusResponse(
        connected=cred is not None,
        email_address=cred.email_address if cred else None,
    )


@router.get("/auth/google", response_model=CalendarAuthUrlResponse)
async def google_calendar_auth(current_user: CurrentUser) -> CalendarAuthUrlResponse:
    settings = get_settings()
    if not settings.GMAIL_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth not configured. Set GMAIL_CLIENT_ID/GMAIL_CLIENT_SECRET "
                   "(Calendar uses the same Google Cloud credentials).",
        )
    redirect_uri = f"{settings.BACKEND_URL}/api/v1/calendar/auth/google/callback"
    state = _make_state_token(str(current_user.id), "gcal")
    params = {
        "client_id": settings.GMAIL_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": " ".join(GCAL_SCOPES),
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return CalendarAuthUrlResponse(
        auth_url=GCAL_AUTH_URL + "?" + urlencode(params),
        message="Open this URL in your browser to connect Google Calendar.",
    )


@router.get("/auth/google/callback")
async def google_calendar_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Database = None,
) -> dict:
    user_id_str, provider = _decode_state_token(state)
    if provider != "gcal":
        raise HTTPException(status_code=400, detail="Provider mismatch in state token")

    settings = get_settings()
    redirect_uri = f"{settings.BACKEND_URL}/api/v1/calendar/auth/google/callback"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            GCAL_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GMAIL_CLIENT_ID,
                "client_secret": settings.GMAIL_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if resp.status_code != 200:
            raise HTTPException(502, detail=f"Google token exchange failed: {resp.text}")
        tokens = resp.json()

    email_address = ""
    async with httpx.AsyncClient(timeout=15) as client:
        user_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        if user_resp.status_code == 200:
            email_address = user_resp.json().get("email", "")

    expiry = None
    if "expires_in" in tokens:
        expiry = datetime.fromtimestamp(
            datetime.now(timezone.utc).timestamp() + tokens["expires_in"], tz=timezone.utc
        )

    user_id = uuid.UUID(user_id_str)
    result = await db.execute(
        select(EmailCredential).where(
            EmailCredential.user_id == user_id, EmailCredential.provider == "gcal"
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.access_token_enc = encrypt_token(tokens["access_token"])
        if "refresh_token" in tokens:
            existing.refresh_token_enc = encrypt_token(tokens["refresh_token"])
        existing.token_expiry = expiry
        existing.email_address = email_address
        existing.is_active = True
        existing.updated_at = datetime.now(timezone.utc)
    else:
        db.add(EmailCredential(
            user_id=user_id,
            provider="gcal",
            email_address=email_address,
            access_token_enc=encrypt_token(tokens["access_token"]),
            refresh_token_enc=encrypt_token(tokens["refresh_token"]) if "refresh_token" in tokens else None,
            token_expiry=expiry,
            scopes=GCAL_SCOPES,
        ))

    await audit.log_action(db, action="calendar.google_connected", user_id=user_id,
                           details={"email": email_address})
    return {"status": "connected", "provider": "gcal", "email": email_address,
            "message": "Google Calendar connected. You can now close this tab."}


@router.get("/events", response_model=EventListResponse)
async def list_events(
    current_user: CurrentUser,
    db: Database,
    days: int = Query(default=7, ge=1, le=60),
) -> EventListResponse:
    (service_cred, agent) = await _get_gcal_service(db, current_user.id)
    service, cred = service_cred
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="Google Calendar not connected. Use /calendar/auth/google.",
        )
    try:
        now = datetime.now(timezone.utc)
        events = await service.list_events(now, now + timedelta(days=days), limit=50)
    finally:
        await agent._sync_tokens(db, cred, service)
    return EventListResponse(
        items=[EventResponse(**e.__dict__) for e in events], total=len(events)
    )


@router.get("/upcoming", response_model=EventListResponse)
async def upcoming_events(
    current_user: CurrentUser,
    db: Database,
    within_minutes: int = Query(default=35, ge=5, le=240),
) -> EventListResponse:
    """Events starting within the window — powers the meeting-prep n8n nudge."""
    (service_cred, agent) = await _get_gcal_service(db, current_user.id)
    service, cred = service_cred
    if service is None:
        return EventListResponse(items=[], total=0)
    try:
        now = datetime.now(timezone.utc)
        events = await service.list_events(
            now, now + timedelta(minutes=within_minutes), limit=10
        )
    finally:
        await agent._sync_tokens(db, cred, service)
    return EventListResponse(
        items=[EventResponse(**e.__dict__) for e in events], total=len(events)
    )


@router.post("/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventCreateRequest,
    current_user: CurrentUser,
    db: Database,
) -> EventResponse:
    (service_cred, agent) = await _get_gcal_service(db, current_user.id)
    service, cred = service_cred
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="Google Calendar not connected. Use /calendar/auth/google.",
        )
    try:
        event = await service.create_event(
            title=payload.title,
            start=payload.start,
            end=payload.start + timedelta(minutes=payload.duration_minutes),
            attendees=payload.attendees,
            location=payload.location,
            description=payload.description,
        )
        await audit.log_action(
            db, action="calendar.schedule", user_id=current_user.id,
            resource_type="calendar_event", resource_id=event.id,
            details={"title": payload.title, "via": "api"},
        )
    finally:
        await agent._sync_tokens(db, cred, service)
    return EventResponse(**event.__dict__)


@router.delete("/disconnect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_calendar(current_user: CurrentUser, db: Database) -> None:
    result = await db.execute(
        select(EmailCredential).where(
            EmailCredential.user_id == current_user.id,
            EmailCredential.provider == "gcal",
        )
    )
    cred = result.scalar_one_or_none()
    if cred:
        await db.delete(cred)
        await audit.log_action(
            db, action="calendar.google_disconnected", user_id=current_user.id
        )
