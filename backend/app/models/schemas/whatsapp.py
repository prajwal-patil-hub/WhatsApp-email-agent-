from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Inbound WhatsApp payloads ─────────────────────────────────────────────────

class WATextContent(BaseModel):
    body: str


class WAAudioContent(BaseModel):
    id: str
    mime_type: str
    voice: bool = False
    sha256: str | None = None


class WAImageContent(BaseModel):
    id: str
    mime_type: str
    sha256: str | None = None
    caption: str | None = None


class WADocumentContent(BaseModel):
    id: str
    mime_type: str
    filename: str | None = None
    sha256: str | None = None
    caption: str | None = None


class WAInboundMessage(BaseModel):
    id: str
    from_: str = Field(alias="from")
    timestamp: str
    type: Literal["text", "audio", "image", "document", "sticker", "video", "reaction"]
    text: WATextContent | None = None
    audio: WAAudioContent | None = None
    image: WAImageContent | None = None
    document: WADocumentContent | None = None

    model_config = {"populate_by_name": True}


class WAContact(BaseModel):
    profile: dict[str, Any]
    wa_id: str


class WAMetadata(BaseModel):
    display_phone_number: str
    phone_number_id: str


class WAValue(BaseModel):
    messaging_product: str
    metadata: WAMetadata
    contacts: list[WAContact] = []
    messages: list[WAInboundMessage] = []
    statuses: list[dict[str, Any]] = []


class WAChange(BaseModel):
    value: WAValue
    field: str


class WAEntry(BaseModel):
    id: str
    changes: list[WAChange]


class WAWebhookPayload(BaseModel):
    object: str
    entry: list[WAEntry]


# ── Outbound WhatsApp payloads ────────────────────────────────────────────────

class WAOutboundTextBody(BaseModel):
    body: str


class WAOutboundMessage(BaseModel):
    messaging_product: str = "whatsapp"
    recipient_type: str = "individual"
    to: str
    type: str = "text"
    text: WAOutboundTextBody


# ── Internal processed event ─────────────────────────────────────────────────

class ProcessedWhatsAppMessage(BaseModel):
    wa_message_id: str
    phone_number: str
    contact_name: str | None
    message_type: str
    content: str
    media_id: str | None = None
    timestamp: str
