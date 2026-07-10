"""Integration tests for research, briefing, and admin routes — Phases 5–7."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


# ── research ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_research_unauthenticated(client: AsyncClient):
    resp = await client.post("/api/v1/research", json={"question": "x"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_research_runs_agent(client: AsyncClient, auth_headers):
    with patch(
        "app.agents.research_agent.ResearchAgent.handle_command", new_callable=AsyncMock
    ) as mock_handle:
        mock_handle.return_value = "🔍 *Research Report*\n\nFindings [1]."
        resp = await client.post(
            "/api/v1/research", json={"question": "compare X and Y"}, headers=auth_headers
        )
    assert resp.status_code == 200
    assert "Research Report" in resp.json()["report"]


@pytest.mark.asyncio
async def test_research_reports_empty(client: AsyncClient, auth_headers):
    resp = await client.get("/api/v1/research/reports", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# ── briefing ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_briefing_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/v1/briefing")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_briefing_returns_text(client: AsyncClient, auth_headers):
    resp = await client.get("/api/v1/briefing", headers=auth_headers)
    assert resp.status_code == 200
    assert "Executive Briefing" in resp.json()["briefing"]


# ── admin (test_user fixture is role=admin) ───────────────────────────────────

@pytest.mark.asyncio
async def test_admin_audit_log(client: AsyncClient, auth_headers):
    # briefing call above logs an action; here just verify shape + auth
    resp = await client.get("/api/v1/admin/audit", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data and "total" in data


@pytest.mark.asyncio
async def test_admin_users(client: AsyncClient, auth_headers):
    resp = await client.get("/api/v1/admin/users", headers=auth_headers)
    assert resp.status_code == 200
    users = resp.json()["items"]
    assert any(u["role"] == "admin" for u in users)


@pytest.mark.asyncio
async def test_admin_system_health(client: AsyncClient, auth_headers):
    resp = await client.get("/api/v1/admin/system/health", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["postgres"] == "ok"  # test DB responds
    assert set(data.keys()) == {"postgres", "redis", "qdrant", "ollama"}


@pytest.mark.asyncio
async def test_admin_analytics_messages(client: AsyncClient, auth_headers):
    resp = await client.get("/api/v1/admin/analytics/messages", headers=auth_headers)
    assert resp.status_code == 200
    assert "days" in resp.json()


@pytest.mark.asyncio
async def test_admin_analytics_tasks(client: AsyncClient, auth_headers):
    await client.post("/api/v1/tasks", json={"title": "T1"}, headers=auth_headers)
    resp = await client.get("/api/v1/admin/analytics/tasks", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["pending"] >= 1


@pytest.mark.asyncio
async def test_admin_requires_admin_role(client: AsyncClient, db_session):
    """Non-admin token gets 403 on admin endpoints."""
    import datetime as dt
    from datetime import timezone

    from app.core.security import create_access_token, decode_token
    from app.models.db.session import Session
    from app.models.db.user import User

    user = User(phone_number="15550001111", role="user")
    db_session.add(user)
    await db_session.flush()
    token = create_access_token(str(user.id), role="user")
    decoded = decode_token(token)
    db_session.add(Session(
        user_id=user.id,
        token_jti=decoded["jti"],
        expires_at=dt.datetime.fromtimestamp(decoded["exp"], tz=timezone.utc),
    ))
    await db_session.flush()

    resp = await client.get(
        "/api/v1/admin/audit", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403
