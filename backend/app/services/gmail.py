"""Gmail provider — google-api-python-client with async wrapper."""

import asyncio
import base64
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime
from typing import Any

from app.services.email_provider import EmailMessage, EmailProvider, EmailThread

try:
    import google.auth.transport.requests
    import google.oauth2.credentials
    from googleapiclient.discovery import build as _google_build
    _GOOGLE_AVAILABLE = True
except ImportError:
    _GOOGLE_AVAILABLE = False

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]
GMAIL_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GMAIL_TOKEN_URL = "https://oauth2.googleapis.com/token"


class GmailProvider(EmailProvider):
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        access_token: str,
        refresh_token: str,
        token_expiry: datetime | None,
    ) -> None:
        if not _GOOGLE_AVAILABLE:
            raise RuntimeError(
                "Install google-auth-oauthlib and google-api-python-client to use Gmail."
            )
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
        creds = google.oauth2.credentials.Credentials(
            token=self._access_token,
            refresh_token=self._refresh_token,
            token_uri=GMAIL_TOKEN_URL,
            client_id=self._client_id,
            client_secret=self._client_secret,
            scopes=GMAIL_SCOPES,
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(google.auth.transport.requests.Request())
            self.token_refreshed = True
            self.new_access_token = creds.token
            self.new_token_expiry = creds.expiry
            self._access_token = creds.token
        return _google_build("gmail", "v1", credentials=creds)

    @staticmethod
    def _parse_message(raw: dict[str, Any]) -> EmailMessage:
        headers = {
            h["name"].lower(): h["value"]
            for h in raw.get("payload", {}).get("headers", [])
        }
        body_text = ""
        payload = raw.get("payload", {})
        if payload.get("mimeType") == "text/plain":
            data = payload.get("body", {}).get("data", "")
            body_text = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        elif "parts" in payload:
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain":
                    data = part.get("body", {}).get("data", "")
                    body_text = base64.urlsafe_b64decode(data + "==").decode(
                        "utf-8", errors="replace"
                    )
                    break

        sender_raw = headers.get("from", "")
        if "<" in sender_raw:
            sender_name = sender_raw.split("<")[0].strip().strip('"')
            sender_email = sender_raw.split("<")[1].rstrip(">").strip()
        else:
            sender_name = sender_raw
            sender_email = sender_raw

        received_at = datetime.now(timezone.utc)
        internal_date = raw.get("internalDate")
        if internal_date:
            received_at = datetime.fromtimestamp(int(internal_date) / 1000, tz=timezone.utc)
        else:
            date_str = headers.get("date", "")
            if date_str:
                try:
                    received_at = parsedate_to_datetime(date_str)
                except Exception:
                    pass

        return EmailMessage(
            id=raw["id"],
            thread_id=raw.get("threadId", ""),
            subject=headers.get("subject", "(no subject)"),
            sender=sender_name,
            sender_email=sender_email,
            snippet=raw.get("snippet", ""),
            body_text=body_text[:4000],
            received_at=received_at,
            is_read="UNREAD" not in raw.get("labelIds", []),
            labels=raw.get("labelIds", []),
            message_id_header=headers.get("message-id", ""),
        )

    async def get_unread(self, limit: int = 10) -> list[EmailMessage]:
        def _sync() -> list[EmailMessage]:
            service = self._build_service()
            result = (
                service.users().messages()
                .list(userId="me", q="is:unread", maxResults=limit, labelIds=["INBOX"])
                .execute()
            )
            msgs = []
            for ref in result.get("messages", []):
                msg = (
                    service.users().messages()
                    .get(userId="me", id=ref["id"], format="full")
                    .execute()
                )
                msgs.append(self._parse_message(msg))
            return msgs
        return await asyncio.to_thread(_sync)

    async def get_thread(self, thread_id: str) -> EmailThread:
        def _sync() -> EmailThread:
            service = self._build_service()
            thread = (
                service.users().threads()
                .get(userId="me", id=thread_id, format="full")
                .execute()
            )
            msgs = [self._parse_message(m) for m in thread.get("messages", [])]
            return EmailThread(thread_id=thread_id, messages=msgs)
        return await asyncio.to_thread(_sync)

    async def send(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
        reply_to_message_id: str | None = None,
    ) -> str:
        def _sync() -> str:
            service = self._build_service()
            mime_msg = MIMEText(body)
            mime_msg["to"] = to
            mime_msg["subject"] = subject
            if reply_to_message_id:
                mime_msg["In-Reply-To"] = reply_to_message_id
                mime_msg["References"] = reply_to_message_id
            raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode()
            payload: dict[str, Any] = {"raw": raw}
            if thread_id:
                payload["threadId"] = thread_id
            result = service.users().messages().send(userId="me", body=payload).execute()
            return result["id"]
        return await asyncio.to_thread(_sync)

    async def mark_as_read(self, message_id: str) -> None:
        def _sync() -> None:
            service = self._build_service()
            service.users().messages().modify(
                userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}
            ).execute()
        await asyncio.to_thread(_sync)
