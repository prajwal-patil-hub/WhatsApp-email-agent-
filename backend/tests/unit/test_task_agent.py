"""Unit tests for TaskAgent — Phase 3."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.agents.task_agent import TaskAgent
from app.models.db.task import Task
from app.models.db.user import User


def _chat_json(payload: dict):
    return AsyncMock(return_value={
        "content": json.dumps(payload), "model": "test", "tokens_used": 10,
    })


@pytest.fixture
def mock_ollama():
    svc = MagicMock()
    svc.chat = _chat_json({"action": "unknown"})
    return svc


@pytest.fixture
def agent(mock_ollama, mock_settings):
    return TaskAgent(ollama=mock_ollama)


@pytest_asyncio.fixture
async def task_user(db_session):
    user = User(phone_number="19995550000", role="user")
    db_session.add(user)
    await db_session.flush()
    return user


# ── create ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_task_with_priority_and_due(agent, mock_ollama, db_session, task_user):
    due = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    mock_ollama.chat = _chat_json({
        "action": "create", "title": "Call dentist", "priority": "high",
        "due_date": due, "project": None, "recurrence": None,
    })

    result = await agent.handle_command(
        db_session, task_user.id, "task_create", "add task call dentist tomorrow, important"
    )

    assert "Task created" in result
    assert "Call dentist" in result
    assert "high" in result

    row = (await db_session.execute(
        select(Task).where(Task.user_id == task_user.id)
    )).scalar_one()
    assert row.title == "Call dentist"
    assert row.priority == "high"
    assert row.due_date is not None


@pytest.mark.asyncio
async def test_create_falls_back_to_message_when_no_title(agent, mock_ollama, db_session, task_user):
    mock_ollama.chat = _chat_json({"action": "create", "title": None, "priority": None})

    result = await agent.handle_command(
        db_session, task_user.id, "task_create", "buy groceries"
    )

    assert "Task created" in result
    row = (await db_session.execute(
        select(Task).where(Task.user_id == task_user.id)
    )).scalar_one()
    assert row.title == "buy groceries"
    assert row.priority == "medium"


@pytest.mark.asyncio
async def test_create_invalid_priority_defaults_to_medium(agent, mock_ollama, db_session, task_user):
    mock_ollama.chat = _chat_json({
        "action": "create", "title": "Some task", "priority": "MAXIMUM_URGENT",
    })
    await agent.handle_command(db_session, task_user.id, "task_create", "some task")
    row = (await db_session.execute(
        select(Task).where(Task.user_id == task_user.id)
    )).scalar_one()
    assert row.priority == "medium"


# ── list ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_empty(agent, mock_ollama, db_session, task_user):
    mock_ollama.chat = _chat_json({"action": "list", "status_filter": "pending"})
    result = await agent.handle_command(db_session, task_user.id, "task_list", "show my tasks")
    assert "No tasks" in result


@pytest.mark.asyncio
async def test_list_shows_tasks_with_overdue_flag(agent, mock_ollama, db_session, task_user):
    past = datetime.now(timezone.utc) - timedelta(days=2)
    db_session.add(Task(user_id=task_user.id, title="Overdue thing", priority="urgent", due_date=past))
    db_session.add(Task(user_id=task_user.id, title="No due date", priority="low"))
    await db_session.flush()

    mock_ollama.chat = _chat_json({"action": "list", "status_filter": "pending"})
    result = await agent.handle_command(db_session, task_user.id, "task_list", "show my tasks")

    assert "Your tasks (2)" in result
    assert "Overdue thing" in result
    assert "OVERDUE" in result
    assert "No due date" in result


# ── complete ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_complete_by_number(agent, mock_ollama, db_session, task_user):
    db_session.add(Task(user_id=task_user.id, title="First task"))
    await db_session.flush()

    mock_ollama.chat = _chat_json({"action": "complete", "task_ref": "1"})
    result = await agent.handle_command(db_session, task_user.id, "task_update", "complete task 1")

    assert "Done" in result
    row = (await db_session.execute(
        select(Task).where(Task.user_id == task_user.id)
    )).scalar_one()
    assert row.status == "completed"
    assert row.completed_at is not None


@pytest.mark.asyncio
async def test_complete_by_keyword(agent, mock_ollama, db_session, task_user):
    db_session.add(Task(user_id=task_user.id, title="Call the dentist"))
    db_session.add(Task(user_id=task_user.id, title="Write report"))
    await db_session.flush()

    mock_ollama.chat = _chat_json({"action": "complete", "task_ref": "dentist"})
    result = await agent.handle_command(db_session, task_user.id, "task_update", "finish the dentist one")

    assert "Done" in result
    assert "dentist" in result.lower()


@pytest.mark.asyncio
async def test_complete_recurring_spawns_next(agent, mock_ollama, db_session, task_user):
    due = datetime.now(timezone.utc) + timedelta(hours=1)
    db_session.add(Task(
        user_id=task_user.id, title="Weekly review", recurrence="weekly", due_date=due,
    ))
    await db_session.flush()

    mock_ollama.chat = _chat_json({"action": "complete", "task_ref": "1"})
    result = await agent.handle_command(db_session, task_user.id, "task_update", "complete task 1")

    assert "Next occurrence" in result
    rows = (await db_session.execute(
        select(Task).where(Task.user_id == task_user.id).order_by(Task.created_at)
    )).scalars().all()
    assert len(rows) == 2
    statuses = {r.status for r in rows}
    assert statuses == {"completed", "pending"}
    new_task = [r for r in rows if r.status == "pending"][0]
    assert new_task.recurrence == "weekly"
    assert new_task.due_date is not None


@pytest.mark.asyncio
async def test_complete_unknown_ref(agent, mock_ollama, db_session, task_user):
    mock_ollama.chat = _chat_json({"action": "complete", "task_ref": "99"})
    result = await agent.handle_command(db_session, task_user.id, "task_update", "complete task 99")
    assert "couldn't find" in result.lower()


# ── update ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_priority(agent, mock_ollama, db_session, task_user):
    db_session.add(Task(user_id=task_user.id, title="Prep slides"))
    await db_session.flush()

    mock_ollama.chat = _chat_json({"action": "update", "task_ref": "1", "priority": "urgent"})
    result = await agent.handle_command(
        db_session, task_user.id, "task_update", "make the slides task urgent"
    )

    assert "Updated" in result
    row = (await db_session.execute(
        select(Task).where(Task.user_id == task_user.id)
    )).scalar_one()
    assert row.priority == "urgent"


@pytest.mark.asyncio
async def test_delete_cancels_task(agent, mock_ollama, db_session, task_user):
    db_session.add(Task(user_id=task_user.id, title="Obsolete task"))
    await db_session.flush()

    mock_ollama.chat = _chat_json({"action": "delete", "task_ref": "1"})
    result = await agent.handle_command(db_session, task_user.id, "task_update", "delete task 1")

    assert "Cancelled" in result
    row = (await db_session.execute(
        select(Task).where(Task.user_id == task_user.id)
    )).scalar_one()
    assert row.status == "cancelled"


# ── parse robustness ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_llm_garbage_falls_back_to_help(agent, mock_ollama, db_session, task_user):
    mock_ollama.chat = AsyncMock(return_value={
        "content": "I think you want to create a task maybe?", "model": "test", "tokens_used": 10,
    })
    # Unparseable JSON → {} → intent falls back to update with no task_ref
    result = await agent.handle_command(db_session, task_user.id, "task_update", "hmm")
    assert "couldn't find" in result.lower() or "create, list, update" in result


def test_parse_iso_handles_bad_values(agent):
    assert agent._parse_iso(None) is None
    assert agent._parse_iso("not-a-date") is None
    dt = agent._parse_iso("2026-07-10T15:00:00Z")
    assert dt is not None and dt.tzinfo is not None
