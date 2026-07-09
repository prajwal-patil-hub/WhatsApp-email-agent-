"""Task CRUD routes — Phase 3.

The morning_briefing and task_reminders n8n workflows consume these
endpoints, so response shapes ({"items": [...], "total": n}) are stable.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, Database
from app.models.db.task import Task
from app.models.schemas.task import (
    OverdueRemindersResponse,
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    TaskUpdate,
)
from app.services import audit

router = APIRouter(prefix="/tasks", tags=["tasks"])

VALID_PRIORITIES = ("urgent", "high", "medium", "low")
VALID_STATUSES = ("pending", "in_progress", "completed", "cancelled")


async def _get_owned_task(db, user_id: uuid.UUID, task_id: uuid.UUID) -> Task:
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    current_user: CurrentUser,
    db: Database,
    status_filter: str | None = Query(default=None, alias="status"),
    priority: str | None = Query(default=None),
    project: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> TaskListResponse:
    query = select(Task).where(Task.user_id == current_user.id)
    count_query = select(func.count(Task.id)).where(Task.user_id == current_user.id)

    if status_filter:
        query = query.where(Task.status == status_filter)
        count_query = count_query.where(Task.status == status_filter)
    if priority:
        query = query.where(Task.priority == priority)
        count_query = count_query.where(Task.priority == priority)
    if project:
        query = query.where(Task.project == project)
        count_query = count_query.where(Task.project == project)

    query = query.order_by(Task.due_date.asc().nulls_last(), Task.created_at.asc())
    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    tasks = list(result.scalars().all())
    total = (await db.execute(count_query)).scalar_one()

    return TaskListResponse(
        items=[TaskResponse.model_validate(t) for t in tasks], total=total
    )


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
    current_user: CurrentUser,
    db: Database,
) -> TaskResponse:
    if payload.priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=422, detail=f"priority must be one of {VALID_PRIORITIES}")

    task = Task(
        user_id=current_user.id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        due_date=payload.due_date,
        project=payload.project,
        tags=payload.tags,
        recurrence=payload.recurrence,
        source_channel="api",
    )
    db.add(task)
    await db.flush()
    await audit.log_action(
        db, action="task.create", user_id=current_user.id,
        resource_type="task", resource_id=str(task.id),
        details={"title": task.title, "via": "api"},
    )
    return TaskResponse.model_validate(task)


@router.get("/overdue", response_model=OverdueRemindersResponse)
async def get_overdue_reminders(
    current_user: CurrentUser,
    db: Database,
    mark_reminded: bool = Query(default=False),
) -> OverdueRemindersResponse:
    """Overdue pending tasks not yet reminded. n8n polls this hourly with
    mark_reminded=true so each task only nudges once."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Task).where(
            Task.user_id == current_user.id,
            Task.status == "pending",
            Task.due_date.isnot(None),
            Task.due_date < now,
            Task.reminder_sent_at.is_(None),
        ).order_by(Task.due_date.asc())
    )
    tasks = list(result.scalars().all())

    if mark_reminded and tasks:
        for t in tasks:
            t.reminder_sent_at = now
        await db.flush()
        await audit.log_action(
            db, action="task.reminders_sent", user_id=current_user.id,
            details={"count": len(tasks)},
        )

    return OverdueRemindersResponse(
        items=[TaskResponse.model_validate(t) for t in tasks], total=len(tasks)
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID,
    current_user: CurrentUser,
    db: Database,
) -> TaskResponse:
    task = await _get_owned_task(db, current_user.id, task_id)
    return TaskResponse.model_validate(task)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    current_user: CurrentUser,
    db: Database,
) -> TaskResponse:
    task = await _get_owned_task(db, current_user.id, task_id)

    updates = payload.model_dump(exclude_unset=True)
    if "priority" in updates and updates["priority"] not in VALID_PRIORITIES:
        raise HTTPException(status_code=422, detail=f"priority must be one of {VALID_PRIORITIES}")
    if "status" in updates and updates["status"] not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {VALID_STATUSES}")

    for field, value in updates.items():
        setattr(task, field, value)
    if updates.get("status") == "completed" and task.completed_at is None:
        task.completed_at = datetime.now(timezone.utc)

    await db.flush()
    await audit.log_action(
        db, action="task.update", user_id=current_user.id,
        resource_type="task", resource_id=str(task.id),
        details={"fields": list(updates.keys())},
    )
    return TaskResponse.model_validate(task)


@router.post("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: uuid.UUID,
    current_user: CurrentUser,
    db: Database,
) -> TaskResponse:
    task = await _get_owned_task(db, current_user.id, task_id)
    task.status = "completed"
    task.completed_at = datetime.now(timezone.utc)
    await db.flush()
    await audit.log_action(
        db, action="task.complete", user_id=current_user.id,
        resource_type="task", resource_id=str(task.id),
    )
    return TaskResponse.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: uuid.UUID,
    current_user: CurrentUser,
    db: Database,
) -> None:
    task = await _get_owned_task(db, current_user.id, task_id)
    task.status = "cancelled"
    await db.flush()
    await audit.log_action(
        db, action="task.cancel", user_id=current_user.id,
        resource_type="task", resource_id=str(task.id),
    )
