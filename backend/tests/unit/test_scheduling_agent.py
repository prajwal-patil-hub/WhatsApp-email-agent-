"""Unit tests for SchedulingAgent — Phase 4."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.scheduling_agent import SchedulingAgent
from app.services.gcal import CalendarEvent


def _chat_json(payload: dict):
    return AsyncMock(return_value={
        "content": json.dumps(payload), "model": "test", "tokens_used": 10,
    })


def _event(title="Standup", start=None, minutes=30, attendees=None):
    start = start or datetime(2026, 7, 10, 9, 0, tzinfo=timezone.utc)
    return CalendarEvent(
        id="evt1", title=title, start=start,
        end=start + timedelta(minutes=minutes),
        attendees=attendees or [], location=None, link=None,
    )


@pytest.fixture
def mock_ollama():
    svc = MagicMock()
    svc.chat = _chat_json({"action": "unknown"})
    return svc


@pytest.fixture
def agent(mock_ollama, mock_settings):
    return SchedulingAgent(ollama=mock_ollama)


@pytest.fixture
def mock_service():
    svc = MagicMock()
    svc.token_refreshed = False
    svc.list_events = AsyncMock(return_value=[])
    svc.create_event = AsyncMock(return_value=_event(title="Sync with John"))
    return svc


@pytest.mark.asyncio
async def test_not_connected_message(agent, db_session):
    with patch.object(agent, "_get_service_and_credential", return_value=(None, None)):
        result = await agent.handle_command(
            db_session, uuid.uuid4(), "calendar_query", "what's on today?"
        )
    assert "not connected" in result.lower()
    assert "/calendar/auth/google" in result


@pytest.mark.asyncio
async def test_schedule_creates_event(agent, mock_ollama, mock_service, db_session):
    start = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0)
    mock_ollama.chat = _chat_json({
        "action": "schedule", "title": "Sync with John",
        "start": start.isoformat(), "duration_minutes": 30,
        "attendees": ["john@example.com"], "location": None,
    })

    with patch.object(agent, "_get_service_and_credential", return_value=(mock_service, MagicMock())):
        with patch.object(agent, "_sync_tokens", new_callable=AsyncMock):
            result = await agent.handle_command(
                db_session, uuid.uuid4(), "calendar_schedule",
                "schedule 30min sync with john@example.com tomorrow",
            )

    assert "Scheduled" in result
    assert "Sync with John" in result
    mock_service.create_event.assert_awaited_once()
    kwargs = mock_service.create_event.await_args.kwargs
    assert kwargs["attendees"] == ["john@example.com"]
    assert (kwargs["end"] - kwargs["start"]) == timedelta(minutes=30)


@pytest.mark.asyncio
async def test_schedule_missing_time_asks_for_it(agent, mock_ollama, mock_service, db_session):
    mock_ollama.chat = _chat_json({"action": "schedule", "title": "Meeting", "start": None})
    with patch.object(agent, "_get_service_and_credential", return_value=(mock_service, MagicMock())):
        with patch.object(agent, "_sync_tokens", new_callable=AsyncMock):
            result = await agent.handle_command(
                db_session, uuid.uuid4(), "calendar_schedule", "schedule a meeting"
            )
    assert "title and a time" in result
    mock_service.create_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_schedule_flags_conflicts(agent, mock_ollama, mock_service, db_session):
    start = datetime.now(timezone.utc) + timedelta(days=1)
    mock_ollama.chat = _chat_json({
        "action": "schedule", "title": "New mtg", "start": start.isoformat(),
        "duration_minutes": 60, "attendees": [],
    })
    mock_service.list_events = AsyncMock(return_value=[_event(title="Existing standup")])

    with patch.object(agent, "_get_service_and_credential", return_value=(mock_service, MagicMock())):
        with patch.object(agent, "_sync_tokens", new_callable=AsyncMock):
            result = await agent.handle_command(
                db_session, uuid.uuid4(), "calendar_schedule", "book new mtg tomorrow"
            )

    assert "overlaps with" in result
    assert "Existing standup" in result


@pytest.mark.asyncio
async def test_query_empty_day(agent, mock_ollama, mock_service, db_session):
    mock_ollama.chat = _chat_json({"action": "query", "query_date": None})
    with patch.object(agent, "_get_service_and_credential", return_value=(mock_service, MagicMock())):
        with patch.object(agent, "_sync_tokens", new_callable=AsyncMock):
            result = await agent.handle_command(
                db_session, uuid.uuid4(), "calendar_query", "what's on today?"
            )
    assert "No events" in result


@pytest.mark.asyncio
async def test_query_lists_events(agent, mock_ollama, mock_service, db_session):
    mock_ollama.chat = _chat_json({"action": "query", "query_date": "2026-07-10"})
    mock_service.list_events = AsyncMock(return_value=[
        _event(title="Standup"),
        _event(title="1:1 with boss", start=datetime(2026, 7, 10, 14, 0, tzinfo=timezone.utc),
               attendees=["boss@co.com"]),
    ])
    with patch.object(agent, "_get_service_and_credential", return_value=(mock_service, MagicMock())):
        with patch.object(agent, "_sync_tokens", new_callable=AsyncMock):
            result = await agent.handle_command(
                db_session, uuid.uuid4(), "calendar_query", "agenda for July 10"
            )
    assert "2 events" in result
    assert "Standup" in result
    assert "1:1 with boss" in result
    assert "(1 attendees)" in result


@pytest.mark.asyncio
async def test_service_error_returns_friendly_message(agent, mock_ollama, mock_service, db_session):
    mock_ollama.chat = _chat_json({"action": "query", "query_date": None})
    mock_service.list_events = AsyncMock(side_effect=RuntimeError("google api 500"))
    with patch.object(agent, "_get_service_and_credential", return_value=(mock_service, MagicMock())):
        with patch.object(agent, "_sync_tokens", new_callable=AsyncMock):
            result = await agent.handle_command(
                db_session, uuid.uuid4(), "calendar_query", "agenda"
            )
    assert "⚠️" in result
