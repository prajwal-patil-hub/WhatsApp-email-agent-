"""Admin + analytics routes — Phase 6. All endpoints require the admin role."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import AdminUser, Database
from app.models.db.audit import AuditLog
from app.models.db.message import Message
from app.models.db.task import Task
from app.models.db.user import User

router = APIRouter(prefix="/admin", tags=["admin"])


class AuditEntry(BaseModel):
    id: uuid.UUID
    action: str
    resource_type: str | None
    resource_id: str | None
    status: str
    user_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditListResponse(BaseModel):
    items: list[AuditEntry]
    total: int


class UserEntry(BaseModel):
    id: uuid.UUID
    phone_number: str
    name: str | None
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    items: list[UserEntry]
    total: int


class SystemHealthResponse(BaseModel):
    postgres: str
    redis: str
    qdrant: str
    ollama: str


class DayCount(BaseModel):
    date: str
    count: int


class MessageAnalyticsResponse(BaseModel):
    days: list[DayCount]
    total: int


class TaskAnalyticsResponse(BaseModel):
    pending: int
    in_progress: int
    completed: int
    cancelled: int
    completed_last_7_days: int


@router.get("/audit", response_model=AuditListResponse)
async def get_audit_log(
    admin: AdminUser,
    db: Database,
    action: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AuditListResponse:
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    count_query = select(func.count(AuditLog.id))
    if action:
        query = query.where(AuditLog.action.like(f"{action}%"))
        count_query = count_query.where(AuditLog.action.like(f"{action}%"))
    result = await db.execute(query.limit(limit).offset(offset))
    total = (await db.execute(count_query)).scalar_one()
    return AuditListResponse(
        items=[AuditEntry.model_validate(a) for a in result.scalars().all()],
        total=total,
    )


@router.get("/users", response_model=UserListResponse)
async def list_users(admin: AdminUser, db: Database) -> UserListResponse:
    result = await db.execute(select(User).order_by(User.created_at.asc()))
    users = list(result.scalars().all())
    return UserListResponse(
        items=[UserEntry.model_validate(u) for u in users], total=len(users)
    )


@router.get("/system/health", response_model=SystemHealthResponse)
async def system_health(admin: AdminUser, db: Database) -> SystemHealthResponse:
    from sqlalchemy import text

    checks = {"postgres": "down", "redis": "down", "qdrant": "down", "ollama": "down"}
    try:
        await db.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception:
        pass
    try:
        from app.memory.short_term import ping

        if await ping():
            checks["redis"] = "ok"
    except Exception:
        pass
    try:
        from app.services.qdrant import get_qdrant_service

        if await get_qdrant_service().is_available():
            checks["qdrant"] = "ok"
    except Exception:
        pass
    try:
        from app.services.ollama import get_ollama_service

        if await get_ollama_service().is_available():
            checks["ollama"] = "ok"
    except Exception:
        pass
    return SystemHealthResponse(**checks)


@router.get("/analytics/messages", response_model=MessageAnalyticsResponse)
async def message_analytics(
    admin: AdminUser,
    db: Database,
    days: int = Query(default=14, ge=1, le=90),
) -> MessageAnalyticsResponse:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            func.date(Message.created_at).label("day"),
            func.count(Message.id).label("count"),
        )
        .where(Message.created_at >= since)
        .group_by(func.date(Message.created_at))
        .order_by(func.date(Message.created_at))
    )
    rows = result.all()
    day_counts = [DayCount(date=str(r.day), count=r.count) for r in rows]
    return MessageAnalyticsResponse(
        days=day_counts, total=sum(d.count for d in day_counts)
    )


@router.get("/analytics/tasks", response_model=TaskAnalyticsResponse)
async def task_analytics(admin: AdminUser, db: Database) -> TaskAnalyticsResponse:
    result = await db.execute(
        select(Task.status, func.count(Task.id)).group_by(Task.status)
    )
    by_status = dict(result.all())

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    completed_week = (
        await db.execute(
            select(func.count(Task.id)).where(
                Task.status == "completed", Task.completed_at >= week_ago
            )
        )
    ).scalar_one()

    return TaskAnalyticsResponse(
        pending=by_status.get("pending", 0),
        in_progress=by_status.get("in_progress", 0),
        completed=by_status.get("completed", 0),
        cancelled=by_status.get("cancelled", 0),
        completed_last_7_days=completed_week,
    )
