"""Integration tests for knowledge + calendar routes — Phase 4."""

import io
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.services.gcal import CalendarEvent


# ── knowledge ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_knowledge_list_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/v1/knowledge")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_knowledge_list_empty(client: AsyncClient, auth_headers):
    resp = await client.get("/api/v1/knowledge", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_knowledge_upload_unsupported_type(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/v1/knowledge/upload",
        files={"file": ("photo.png", io.BytesIO(b"fake"), "image/png")},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_knowledge_upload_txt(client: AsyncClient, auth_headers):
    mock_qdrant = MagicMock()
    mock_qdrant.upsert = AsyncMock(return_value="pt1")
    with (
        patch("app.services.ollama.OllamaService.embed", new_callable=AsyncMock, return_value=[0.1] * 768),
        patch("app.services.qdrant.get_qdrant_service", return_value=mock_qdrant),
    ):
        resp = await client.post(
            "/api/v1/knowledge/upload",
            files={"file": ("notes.txt", io.BytesIO(b"meeting notes content"), "text/plain")},
            data={"title": "meeting notes"},
            headers=auth_headers,
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "meeting notes"
    assert data["status"] == "ready"
    assert data["chunk_count"] == 1


@pytest.mark.asyncio
async def test_knowledge_ask(client: AsyncClient, auth_headers):
    with patch("app.agents.knowledge_agent.KnowledgeAgent.answer", new_callable=AsyncMock) as mock_answer:
        mock_answer.return_value = "The answer is 42. 📎 Sources: notes"
        resp = await client.post(
            "/api/v1/knowledge/ask",
            json={"question": "what is the answer?"},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    assert "42" in resp.json()["answer"]


@pytest.mark.asyncio
async def test_knowledge_delete_not_found(client: AsyncClient, auth_headers):
    resp = await client.delete(
        "/api/v1/knowledge/00000000-0000-0000-0000-000000000000", headers=auth_headers
    )
    assert resp.status_code == 404


# ── calendar ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_calendar_status_not_connected(client: AsyncClient, auth_headers):
    resp = await client.get("/api/v1/calendar/status", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["connected"] is False


@pytest.mark.asyncio
async def test_calendar_auth_not_configured(client: AsyncClient, auth_headers):
    with patch("app.api.routes.calendar.get_settings") as mock_settings:
        s = MagicMock()
        s.GMAIL_CLIENT_ID = None
        mock_settings.return_value = s
        resp = await client.get("/api/v1/calendar/auth/google", headers=auth_headers)
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_calendar_events_not_connected(client: AsyncClient, auth_headers):
    resp = await client.get("/api/v1/calendar/events", headers=auth_headers)
    assert resp.status_code == 412


@pytest.mark.asyncio
async def test_calendar_create_event_with_mocked_service(client: AsyncClient, auth_headers):
    start = datetime.now(timezone.utc) + timedelta(days=1)
    fake_event = CalendarEvent(
        id="evt42", title="Board meeting", start=start,
        end=start + timedelta(minutes=45), attendees=["a@b.com"],
        location="HQ", link="https://cal.google.com/evt42",
    )
    mock_service = MagicMock()
    mock_service.token_refreshed = False
    mock_service.create_event = AsyncMock(return_value=fake_event)

    with patch(
        "app.agents.scheduling_agent.SchedulingAgent._get_service_and_credential",
        new_callable=AsyncMock,
    ) as mock_get:
        mock_get.return_value = (mock_service, MagicMock())
        with patch(
            "app.agents.scheduling_agent.SchedulingAgent._sync_tokens",
            new_callable=AsyncMock,
        ):
            resp = await client.post(
                "/api/v1/calendar/events",
                json={
                    "title": "Board meeting",
                    "start": start.isoformat(),
                    "duration_minutes": 45,
                    "attendees": ["a@b.com"],
                    "location": "HQ",
                },
                headers=auth_headers,
            )

    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Board meeting"
    assert data["id"] == "evt42"


@pytest.mark.asyncio
async def test_calendar_disconnect_when_not_connected(client: AsyncClient, auth_headers):
    resp = await client.delete("/api/v1/calendar/disconnect", headers=auth_headers)
    assert resp.status_code == 204
