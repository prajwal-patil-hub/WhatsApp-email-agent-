import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MemoryCreate(BaseModel):
    memory_type: str = Field(
        ..., pattern="^(preference|contact|fact|goal|habit)$"
    )
    content: str = Field(..., min_length=1, max_length=10000)
    summary: str | None = Field(None, max_length=500)
    importance: float = Field(0.5, ge=0.0, le=1.0)
    expires_at: datetime | None = None
    source: str | None = None


class MemoryUpdate(BaseModel):
    content: str | None = Field(None, min_length=1, max_length=10000)
    summary: str | None = Field(None, max_length=500)
    importance: float | None = Field(None, ge=0.0, le=1.0)
    expires_at: datetime | None = None


class MemoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    memory_type: str
    content: str
    summary: str | None
    importance: float
    access_count: int
    last_accessed: datetime | None
    expires_at: datetime | None
    source: str | None
    created_at: datetime
    updated_at: datetime


class PaginatedMemories(BaseModel):
    items: list[MemoryResponse]
    total: int
