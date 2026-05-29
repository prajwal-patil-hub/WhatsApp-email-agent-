import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MessageBase(BaseModel):
    role: str
    content: str
    message_type: str = "text"


class MessageCreate(MessageBase):
    conversation_id: uuid.UUID
    wa_message_id: str | None = None
    media_url: str | None = None
    transcription: str | None = None


class MessageResponse(MessageBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    wa_message_id: str | None
    media_url: str | None
    transcription: str | None
    tokens_used: int
    model_used: str | None
    processing_ms: int
    created_at: datetime


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    channel: str
    status: str
    title: str | None
    created_at: datetime
    updated_at: datetime


class PaginatedMessages(BaseModel):
    items: list[MessageResponse]
    total: int
    page: int
    size: int


class PaginatedConversations(BaseModel):
    items: list[ConversationResponse]
    total: int
