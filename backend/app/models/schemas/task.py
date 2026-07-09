import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    priority: str = "medium"
    due_date: datetime | None = None
    project: str | None = None
    tags: list[str] = []
    recurrence: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    priority: str | None = None
    status: str | None = None
    due_date: datetime | None = None
    project: str | None = None
    tags: list[str] | None = None
    recurrence: str | None = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    priority: str
    status: str
    due_date: datetime | None
    completed_at: datetime | None
    project: str | None
    tags: list
    recurrence: str | None
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int


class OverdueRemindersResponse(BaseModel):
    items: list[TaskResponse]
    total: int
