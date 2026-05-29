"""Email Agent — Phase 2. Stub with interface defined."""

from dataclasses import dataclass


@dataclass
class EmailSummary:
    subject: str
    sender: str
    preview: str
    priority: str
    received_at: str


@dataclass
class DraftedEmail:
    to: str
    subject: str
    body: str
    thread_id: str | None = None


class EmailAgent:
    """
    Phase 2 implementation will include:
    - Gmail OAuth2 integration
    - Outlook/Office365 OAuth2 integration
    - Read inbox, categorize, summarize
    - Draft and send replies
    - Follow-up tracking
    - Priority detection
    """

    async def get_unread_summary(self, user_id: str, limit: int = 10) -> list[EmailSummary]:
        raise NotImplementedError("Email Agent available in Phase 2")

    async def draft_reply(self, user_id: str, email_id: str, instructions: str) -> DraftedEmail:
        raise NotImplementedError("Email Agent available in Phase 2")

    async def send_email(self, user_id: str, draft: DraftedEmail) -> str:
        raise NotImplementedError("Email Agent available in Phase 2")
