"""Email OAuth + management routes — Phase 2."""

import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.agents.email_agent import EmailAgent, encrypt_token
from app.api.deps import CurrentUser, Database, OllamaClient
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import create_access_token, decode_token
from app.models.db.email_credential import EmailCredential
from app.models.schemas.email import (
    EmailAuthUrlResponse,
    EmailCredentialStatus,
    EmailInboxResponse,
    EmailSendRequest,
    EmailSendResponse,
    EmailStatusResponse,
)
from app.services import audit
from app.services.gmail import GMAIL_AUTH_URL, GMAIL_SCOPES

router = APIRouter(prefix="/email", tags=["email"])
logger = get_logger(__name__)


def _make_state_token(user_id: str, provider: str) -> str:
    return create_access_token(
        subject=user_id,
        extra={"purpose": "oauth_state", "provider": provider},
    )


def _decode_state_token(state: str) -> tuple[str, str]:
    try:
        payload = decode_token(state)
        if payload.get("purpose") != "oauth_state":
            raise ValueError("not an oauth state token")
        return payload["sub"], payload["provider"]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid OAuth state: {exc}",
        ) from exc


@router.get("/status", response_model=EmailStatusResponse)
async def get_email_status(current_user: CurrentUser, db: Database) -> EmailStatusResponse:
    result = await db.execute(
        select(EmailCredential).where(EmailCredential.user_id == current_user.id)
    )
    creds = result.scalars().all()
    return EmailStatusResponse(
        connected=any(c.is_active for c in creds),
        credentials=[
            EmailCredentialStatus(
                provider=c.provider,
                email_address=c.email_address,
                is_active=c.is_active,
                token_expiry=c.token_expiry,
                created_at=c.created_at,
            )
            for c in creds
        ],
    )


@router.get("/auth/gmail", response_model=EmailAuthUrlResponse)
async def gmail_auth_initiate(current_user: CurrentUser) -> EmailAuthUrlResponse:
    settings = get_settings()
    if not settings.GMAIL_CLIENT_ID or not settings.GMAIL_REDIRECT_URI:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gmail OAuth not configured. Set GMAIL_CLIENT_ID and GMAIL_REDIRECT_URI.",
        )
    state = _make_state_token(str(current_user.id), "gmail")
    params = {
        "client_id": settings.GMAIL_CLIENT_ID,
        "redirect_uri": settings.GMAIL_REDIRECT_URI,
        "scope": " ".join(GMAIL_SCOPES),
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    url = GMAIL_AUTH_URL + "?" + urlencode(params)
    return EmailAuthUrlResponse(
        auth_url=url, provider="gmail",
        message="Open this URL in your browser to connect Gmail.",
    )


@router.get("/auth/gmail/callback")
async def gmail_auth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Database = None,
) -> dict:
    user_id_str, provider = _decode_state_token(state)
    if provider != "gmail":
        raise HTTPException(status_code=400, detail="Provider mismatch in state token")

    settings = get_settings()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GMAIL_CLIENT_ID,
                "client_secret": settings.GMAIL_CLIENT_SECRET,
                "redirect_uri": settings.GMAIL_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        if resp.status_code != 200:
            raise HTTPException(502, detail=f"Gmail token exchange failed: {resp.text}")
        tokens = resp.json()

    email_address = ""
    async with httpx.AsyncClient(timeout=15) as client:
        user_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        if user_resp.status_code == 200:
            email_address = user_resp.json().get("email", "")

    expiry: datetime | None = None
    if "expires_in" in tokens:
        expiry = datetime.fromtimestamp(
            datetime.now(timezone.utc).timestamp() + tokens["expires_in"], tz=timezone.utc
        )

    user_id = uuid.UUID(user_id_str)
    result = await db.execute(
        select(EmailCredential).where(
            EmailCredential.user_id == user_id, EmailCredential.provider == "gmail"
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
            provider="gmail",
            email_address=email_address,
            access_token_enc=encrypt_token(tokens["access_token"]),
            refresh_token_enc=encrypt_token(tokens["refresh_token"]) if "refresh_token" in tokens else None,
            token_expiry=expiry,
            scopes=GMAIL_SCOPES,
        ))

    await audit.log_action(db, action="email.gmail_connected", user_id=user_id,
                           details={"email": email_address})
    return {"status": "connected", "provider": "gmail", "email": email_address,
            "message": "Gmail connected successfully. You can now close this tab."}


@router.get("/auth/outlook", response_model=EmailAuthUrlResponse)
async def outlook_auth_initiate(current_user: CurrentUser) -> EmailAuthUrlResponse:
    settings = get_settings()
    if not settings.OUTLOOK_CLIENT_ID or not settings.OUTLOOK_REDIRECT_URI:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Outlook OAuth not configured. Set OUTLOOK_CLIENT_ID and OUTLOOK_REDIRECT_URI.",
        )
    from app.services.outlook import OUTLOOK_AUTH_URL, OUTLOOK_SCOPES
    state = _make_state_token(str(current_user.id), "outlook")
    params = {
        "client_id": settings.OUTLOOK_CLIENT_ID,
        "redirect_uri": settings.OUTLOOK_REDIRECT_URI,
        "scope": " ".join(OUTLOOK_SCOPES),
        "response_type": "code",
        "response_mode": "query",
        "state": state,
    }
    url = OUTLOOK_AUTH_URL.format(tenant=settings.OUTLOOK_TENANT_ID) + "?" + urlencode(params)
    return EmailAuthUrlResponse(
        auth_url=url, provider="outlook",
        message="Open this URL in your browser to connect Outlook.",
    )


@router.get("/auth/outlook/callback")
async def outlook_auth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Database = None,
) -> dict:
    user_id_str, provider = _decode_state_token(state)
    if provider != "outlook":
        raise HTTPException(status_code=400, detail="Provider mismatch in state token")

    settings = get_settings()
    from app.services.outlook import OUTLOOK_SCOPES, OUTLOOK_TOKEN_URL

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            OUTLOOK_TOKEN_URL.format(tenant=settings.OUTLOOK_TENANT_ID),
            data={
                "code": code,
                "client_id": settings.OUTLOOK_CLIENT_ID,
                "client_secret": settings.OUTLOOK_CLIENT_SECRET,
                "redirect_uri": settings.OUTLOOK_REDIRECT_URI,
                "grant_type": "authorization_code",
                "scope": " ".join(OUTLOOK_SCOPES),
            },
        )
        if resp.status_code != 200:
            raise HTTPException(502, detail=f"Outlook token exchange failed: {resp.text}")
        tokens = resp.json()

    email_address = ""
    async with httpx.AsyncClient(timeout=15) as client:
        user_resp = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        if user_resp.status_code == 200:
            data = user_resp.json()
            email_address = data.get("mail") or data.get("userPrincipalName", "")

    expiry: datetime | None = None
    if "expires_in" in tokens:
        expiry = datetime.fromtimestamp(
            datetime.now(timezone.utc).timestamp() + tokens["expires_in"], tz=timezone.utc
        )

    user_id = uuid.UUID(user_id_str)
    result = await db.execute(
        select(EmailCredential).where(
            EmailCredential.user_id == user_id, EmailCredential.provider == "outlook"
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
            provider="outlook",
            email_address=email_address,
            access_token_enc=encrypt_token(tokens["access_token"]),
            refresh_token_enc=encrypt_token(tokens["refresh_token"]) if "refresh_token" in tokens else None,
            token_expiry=expiry,
            scopes=OUTLOOK_SCOPES,
        ))

    await audit.log_action(db, action="email.outlook_connected", user_id=user_id,
                           details={"email": email_address})
    return {"status": "connected", "provider": "outlook", "email": email_address,
            "message": "Outlook connected successfully. You can now close this tab."}


@router.delete("/disconnect/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_email(provider: str, current_user: CurrentUser, db: Database) -> None:
    if provider not in ("gmail", "outlook"):
        raise HTTPException(status_code=400, detail="Provider must be 'gmail' or 'outlook'")
    result = await db.execute(
        select(EmailCredential).where(
            EmailCredential.user_id == current_user.id,
            EmailCredential.provider == provider,
        )
    )
    cred = result.scalar_one_or_none()
    if cred:
        await db.delete(cred)
        await audit.log_action(db, action=f"email.{provider}_disconnected", user_id=current_user.id)


@router.get("/inbox", response_model=EmailInboxResponse)
async def get_inbox(
    current_user: CurrentUser,
    db: Database,
    ollama: OllamaClient,
    limit: int = Query(default=10, ge=1, le=25),
) -> EmailInboxResponse:
    result = await db.execute(
        select(EmailCredential).where(
            EmailCredential.user_id == current_user.id,
            EmailCredential.is_active.is_(True),
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="No email provider connected. Use /email/auth/gmail or /email/auth/outlook.",
        )
    agent = EmailAgent(ollama=ollama)
    summary = await agent.handle_command(db, current_user.id, "email_read", "check my emails")
    import re
    match = re.search(r"\((\d+)\)", summary)
    unread_count = int(match.group(1)) if match else 0
    return EmailInboxResponse(summary=summary, unread_count=unread_count)


@router.post("/send", response_model=EmailSendResponse)
async def send_email_direct(
    request: EmailSendRequest,
    current_user: CurrentUser,
    db: Database,
    ollama: OllamaClient,
) -> EmailSendResponse:
    agent = EmailAgent(ollama=ollama)
    provider, cred = await agent._get_provider_and_credential(db, current_user.id)
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="No email provider connected.",
        )
    try:
        msg_id = await provider.send(
            to=request.to,
            subject=request.subject,
            body=request.body,
            thread_id=request.thread_id,
            reply_to_message_id=request.reply_to_message_id,
        )
        await audit.log_action(db, action="email.send", user_id=current_user.id,
                               details={"to": request.to, "subject": request.subject})
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        await agent._sync_tokens(db, cred, provider)
    return EmailSendResponse(message_id=msg_id, to=request.to, subject=request.subject)
