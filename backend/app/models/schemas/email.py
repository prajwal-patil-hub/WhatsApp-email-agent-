from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EmailCredentialStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    email_address: str
    is_active: bool
    token_expiry: datetime | None
    created_at: datetime


class EmailStatusResponse(BaseModel):
    connected: bool
    credentials: list[EmailCredentialStatus]


class EmailAuthUrlResponse(BaseModel):
    auth_url: str
    provider: str
    message: str


class EmailSendRequest(BaseModel):
    to: str
    subject: str
    body: str
    thread_id: str | None = None
    reply_to_message_id: str | None = None


class EmailSendResponse(BaseModel):
    message_id: str
    to: str
    subject: str


class EmailInboxResponse(BaseModel):
    summary: str
    unread_count: int
