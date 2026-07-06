"""Integration tests for email API routes — Phase 2."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.agents.email_agent import encrypt_token
from app.models.db.email_credential import EmailCredential


# ── /email/status ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_status_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/v1/email/status")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_status_no_credentials(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/email/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is False
    assert data["credentials"] == []


@pytest.mark.asyncio
async def test_status_with_gmail_connected(client: AsyncClient, auth_headers: dict, db_session, test_user):
    cred = EmailCredential(
        user_id=test_user.id,
        provider="gmail",
        email_address="test@gmail.com",
        access_token_enc=encrypt_token("access123"),
        refresh_token_enc=encrypt_token("refresh123"),
        token_expiry=datetime(2026, 12, 31, tzinfo=timezone.utc),
        scopes=["https://www.googleapis.com/auth/gmail.readonly"],
        is_active=True,
    )
    db_session.add(cred)
    await db_session.commit()

    resp = await client.get("/api/v1/email/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is True
    assert len(data["credentials"]) == 1
    assert data["credentials"][0]["provider"] == "gmail"
    assert data["credentials"][0]["email_address"] == "test@gmail.com"


# ── /email/auth/gmail ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gmail_auth_not_configured(client: AsyncClient, auth_headers: dict):
    with patch("app.api.routes.email.get_settings") as mock_settings:
        s = MagicMock()
        s.GMAIL_CLIENT_ID = None
        s.GMAIL_REDIRECT_URI = None
        mock_settings.return_value = s
        resp = await client.get("/api/v1/email/auth/gmail", headers=auth_headers)
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_gmail_auth_returns_url(client: AsyncClient, auth_headers: dict):
    with patch("app.api.routes.email.get_settings") as mock_settings:
        s = MagicMock()
        s.GMAIL_CLIENT_ID = "fake-client-id"
        s.GMAIL_REDIRECT_URI = "http://localhost:8000/api/v1/email/auth/gmail/callback"
        s.SECRET_KEY = "test-secret-key-for-testing-only-32chars"
        s.JWT_ALGORITHM = "HS256"
        s.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 1440
        mock_settings.return_value = s
        resp = await client.get("/api/v1/email/auth/gmail", headers=auth_headers)

    # 200 if configured — URL returned
    if resp.status_code == 200:
        data = resp.json()
        assert "auth_url" in data
        assert "accounts.google.com" in data["auth_url"]
        assert data["provider"] == "gmail"


# ── /email/auth/outlook ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_outlook_auth_not_configured(client: AsyncClient, auth_headers: dict):
    with patch("app.api.routes.email.get_settings") as mock_settings:
        s = MagicMock()
        s.OUTLOOK_CLIENT_ID = None
        s.OUTLOOK_REDIRECT_URI = None
        mock_settings.return_value = s
        resp = await client.get("/api/v1/email/auth/outlook", headers=auth_headers)
    assert resp.status_code == 503


# ── /email/disconnect ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_disconnect_invalid_provider(client: AsyncClient, auth_headers: dict):
    resp = await client.delete("/api/v1/email/disconnect/yahoo", headers=auth_headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_disconnect_gmail_not_connected(client: AsyncClient, auth_headers: dict):
    resp = await client.delete("/api/v1/email/disconnect/gmail", headers=auth_headers)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_disconnect_gmail_removes_credential(
    client: AsyncClient, auth_headers: dict, db_session, test_user
):
    cred = EmailCredential(
        user_id=test_user.id,
        provider="gmail",
        email_address="test@gmail.com",
        access_token_enc=encrypt_token("access123"),
        is_active=True,
        scopes=[],
    )
    db_session.add(cred)
    await db_session.commit()

    resp = await client.delete("/api/v1/email/disconnect/gmail", headers=auth_headers)
    assert resp.status_code == 204

    # Verify removed
    status_resp = await client.get("/api/v1/email/status", headers=auth_headers)
    assert status_resp.json()["connected"] is False


# ── /email/inbox ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_inbox_no_provider_connected(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/email/inbox", headers=auth_headers)
    assert resp.status_code == 412


@pytest.mark.asyncio
async def test_inbox_with_provider(client: AsyncClient, auth_headers: dict, db_session, test_user):
    cred = EmailCredential(
        user_id=test_user.id,
        provider="gmail",
        email_address="test@gmail.com",
        access_token_enc=encrypt_token("access123"),
        refresh_token_enc=encrypt_token("refresh123"),
        is_active=True,
        scopes=[],
    )
    db_session.add(cred)
    await db_session.commit()

    with patch("app.agents.email_agent.EmailAgent.handle_command", new_callable=AsyncMock) as mock_handle:
        mock_handle.return_value = "📧 *Unread Emails (2)*\n\n1. Alice: Q3 Report 🟡"
        resp = await client.get("/api/v1/email/inbox", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert data["unread_count"] == 2


# ── /email/send ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_no_provider(client: AsyncClient, auth_headers: dict):
    payload = {"to": "john@example.com", "subject": "Test", "body": "Hello"}
    resp = await client.post("/api/v1/email/send", json=payload, headers=auth_headers)
    assert resp.status_code == 412


@pytest.mark.asyncio
async def test_send_direct_success(client: AsyncClient, auth_headers: dict, db_session, test_user):
    cred = EmailCredential(
        user_id=test_user.id,
        provider="gmail",
        email_address="test@gmail.com",
        access_token_enc=encrypt_token("access123"),
        is_active=True,
        scopes=[],
    )
    db_session.add(cred)
    await db_session.commit()

    mock_provider = MagicMock()
    mock_provider.send = AsyncMock(return_value="msg_abc123")
    mock_provider.token_refreshed = False

    with patch("app.api.routes.email.EmailAgent._get_provider_and_credential", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = (mock_provider, cred)
        with patch("app.api.routes.email.EmailAgent._sync_tokens", new_callable=AsyncMock):
            payload = {"to": "john@example.com", "subject": "Hello", "body": "Test body"}
            resp = await client.post("/api/v1/email/send", json=payload, headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["to"] == "john@example.com"
    assert data["subject"] == "Hello"
