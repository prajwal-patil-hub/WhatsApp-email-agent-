"""Outlook/Microsoft 365 provider — MSAL for auth, httpx for Graph API."""

import asyncio
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from app.services.email_provider import EmailMessage, EmailProvider, EmailThread

try:
    import msal
    _MSAL_AVAILABLE = True
except ImportError:
    _MSAL_AVAILABLE = False

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
OUTLOOK_SCOPES = [
    "https://graph.microsoft.com/Mail.Read",
    "https://graph.microsoft.com/Mail.Send",
    "https://graph.microsoft.com/Mail.ReadWrite",
    "offline_access",
]
OUTLOOK_AUTH_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
OUTLOOK_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"

_HTML_TAG_RE = re.compile(r"<[^>]+>")


class OutlookProvider(EmailProvider):
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        tenant_id: str,
        access_token: str,
        refresh_token: str,
        token_expiry: datetime | None,
    ) -> None:
        if not _MSAL_AVAILABLE:
            raise RuntimeError("Install msal to use Outlook integration.")
        self._client_id = client_id
        self._client_secret = client_secret
        self._tenant_id = tenant_id
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._token_expiry = token_expiry
        self.token_refreshed = False
        self.new_access_token: str | None = None
        self.new_refresh_token: str | None = None
        self.new_token_expiry: datetime | None = None

    def _refresh_if_needed(self) -> str:
        now = datetime.now(timezone.utc)
        if self._token_expiry and self._token_expiry > now:
            return self._access_token

        app = msal.ConfidentialClientApplication(
            client_id=self._client_id,
            client_credential=self._client_secret,
            authority=f"https://login.microsoftonline.com/{self._tenant_id}",
        )
        result = app.acquire_token_by_refresh_token(
            refresh_token=self._refresh_token, scopes=OUTLOOK_SCOPES
        )
        if "access_token" not in result:
            raise RuntimeError(
                f"Outlook token refresh failed: {result.get('error_description', 'unknown')}"
            )
        self._access_token = result["access_token"]
        if "refresh_token" in result:
            self._refresh_token = result["refresh_token"]
            self.new_refresh_token = result["refresh_token"]
        expires_in = result.get("expires_in", 3600)
        expiry = datetime.fromtimestamp(now.timestamp() + expires_in, tz=timezone.utc)
        self._token_expiry = expiry
        self.token_refreshed = True
        self.new_access_token = self._access_token
        self.new_token_expiry = expiry
        return self._access_token

    def _parse_message(self, raw: dict[str, Any]) -> EmailMessage:
        sender = raw.get("from", {}).get("emailAddress", {})
        received_str = raw.get("receivedDateTime", "")
        try:
            received_at = datetime.fromisoformat(received_str.replace("Z", "+00:00"))
        except Exception:
            received_at = datetime.now(timezone.utc)
        body = raw.get("body", {})
        body_text = body.get("content", "")
        if body.get("contentType") == "html":
            body_text = _HTML_TAG_RE.sub("", body_text)
        body_text = body_text[:4000]
        return EmailMessage(
            id=raw["id"],
            thread_id=raw.get("conversationId", raw["id"]),
            subject=raw.get("subject", "(no subject)"),
            sender=sender.get("name", ""),
            sender_email=sender.get("address", ""),
            snippet=raw.get("bodyPreview", "")[:200],
            body_text=body_text,
            received_at=received_at,
            is_read=raw.get("isRead", False),
            labels=raw.get("categories", []),
            message_id_header=raw.get("internetMessageId", ""),
        )

    async def get_unread(self, limit: int = 10) -> list[EmailMessage]:
        token = await asyncio.to_thread(self._refresh_if_needed)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{GRAPH_BASE}/me/mailFolders/inbox/messages",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "$filter": "isRead eq false",
                    "$top": str(limit),
                    "$orderby": "receivedDateTime desc",
                    "$select": (
                        "id,subject,from,receivedDateTime,bodyPreview,"
                        "isRead,conversationId,body,categories,internetMessageId"
                    ),
                },
            )
            resp.raise_for_status()
            return [self._parse_message(m) for m in resp.json().get("value", [])]

    async def get_thread(self, thread_id: str) -> EmailThread:
        token = await asyncio.to_thread(self._refresh_if_needed)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{GRAPH_BASE}/me/messages",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "$filter": f"conversationId eq '{thread_id}'",
                    "$orderby": "receivedDateTime asc",
                    "$select": (
                        "id,subject,from,receivedDateTime,bodyPreview,"
                        "isRead,conversationId,body,internetMessageId"
                    ),
                },
            )
            resp.raise_for_status()
            msgs = [self._parse_message(m) for m in resp.json().get("value", [])]
            return EmailThread(thread_id=thread_id, messages=msgs)

    async def send(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
        reply_to_message_id: str | None = None,
    ) -> str:
        token = await asyncio.to_thread(self._refresh_if_needed)
        payload: dict[str, Any] = {
            "message": {
                "subject": subject,
                "body": {"contentType": "text", "content": body},
                "toRecipients": [{"emailAddress": {"address": to}}],
            }
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{GRAPH_BASE}/me/sendMail",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
        return "sent"

    async def mark_as_read(self, message_id: str) -> None:
        token = await asyncio.to_thread(self._refresh_if_needed)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.patch(
                f"{GRAPH_BASE}/me/messages/{message_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"isRead": True},
            )
            resp.raise_for_status()
