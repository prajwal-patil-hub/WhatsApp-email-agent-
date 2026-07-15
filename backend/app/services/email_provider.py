"""Abstract email provider interface and shared data types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EmailMessage:
    id: str
    thread_id: str
    subject: str
    sender: str
    sender_email: str
    snippet: str
    body_text: str
    received_at: datetime
    is_read: bool
    labels: list[str] = field(default_factory=list)
    message_id_header: str = ""


@dataclass
class EmailThread:
    thread_id: str
    messages: list[EmailMessage]


class EmailProvider(ABC):
    """Common interface for Gmail and Outlook.

    After any operation, check `token_refreshed` and persist updated tokens.
    """

    token_refreshed: bool = False
    new_access_token: str | None = None
    new_refresh_token: str | None = None
    new_token_expiry: datetime | None = None

    @abstractmethod
    async def get_unread(self, limit: int = 10) -> list[EmailMessage]: ...

    @abstractmethod
    async def get_thread(self, thread_id: str) -> EmailThread: ...

    @abstractmethod
    async def send(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
        reply_to_message_id: str | None = None,
    ) -> str: ...

    @abstractmethod
    async def mark_as_read(self, message_id: str) -> None: ...
