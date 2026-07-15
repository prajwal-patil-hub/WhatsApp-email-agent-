"""Unit tests for the briefing service — Phase 7."""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from app.models.db.task import Task
from app.models.db.user import User
from app.services.briefing import build_briefing


@pytest_asyncio.fixture
async def briefing_user(db_session):
    user = User(phone_number="16665550000", role="user")
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_briefing_empty_state(db_session, briefing_user, mock_settings):
    text = await build_briefing(db_session, briefing_user.id)
    assert "Executive Briefing" in text
    assert "Nothing pending" in text


@pytest.mark.asyncio
async def test_briefing_with_tasks(db_session, briefing_user, mock_settings):
    now = datetime.now(timezone.utc)
    db_session.add(Task(user_id=briefing_user.id, title="Overdue report",
                        priority="urgent", due_date=now - timedelta(days=1)))
    db_session.add(Task(user_id=briefing_user.id, title="Someday item", priority="low"))
    await db_session.flush()

    text = await build_briefing(db_session, briefing_user.id)
    assert "Tasks (2 pending)" in text
    assert "Overdue report" in text
    assert "Overdue" in text
    assert "Someday item" in text


@pytest.mark.asyncio
async def test_briefing_calendar_section_absent_when_not_connected(
    db_session, briefing_user, mock_settings
):
    text = await build_briefing(db_session, briefing_user.id)
    # No gcal credential → section silently omitted, briefing still builds
    assert "Executive Briefing" in text
    assert "Calendar" not in text
