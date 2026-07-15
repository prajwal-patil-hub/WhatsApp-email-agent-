"""Unit tests for EmailAgent — Phase 2."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.email_agent import EmailAgent, decrypt_token, encrypt_token
from app.services.email_provider import EmailMessage, EmailThread


# ── Token encryption ──────────────────────────────────────────────────────────

def test_encrypt_decrypt_roundtrip(mock_settings):
    plaintext = "ya29.very-secret-access-token"
    ciphertext = encrypt_token(plaintext)
    assert ciphertext != plaintext
    assert decrypt_token(ciphertext) == plaintext


def test_encrypt_produces_different_ciphertext_each_call(mock_settings):
    plaintext = "same-token"
    c1 = encrypt_token(plaintext)
    c2 = encrypt_token(plaintext)
    # Fernet uses random IVs so ciphertexts differ
    assert c1 != c2
    assert decrypt_token(c1) == decrypt_token(c2) == plaintext


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_ollama():
    svc = MagicMock()
    svc.chat = AsyncMock(
        return_value={"content": "mocked response", "model": "test", "tokens_used": 10}
    )
    return svc


@pytest.fixture
def agent(mock_ollama, mock_settings):
    return EmailAgent(ollama=mock_ollama)


@pytest.fixture
def sample_messages():
    return [
        EmailMessage(
            id="msg1", thread_id="thread1", subject="Q3 Report",
            sender="Alice", sender_email="alice@example.com",
            snippet="Please review the attached Q3 report...",
            body_text="Hi,\n\nPlease review Q3 report.\n\nBest, Alice",
            received_at=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
            is_read=False,
        ),
        EmailMessage(
            id="msg2", thread_id="thread2", subject="Lunch tomorrow?",
            sender="Bob", sender_email="bob@example.com",
            snippet="Are you free for lunch tomorrow at noon?",
            body_text="Are you free for lunch tomorrow at noon?",
            received_at=datetime(2026, 6, 1, 8, 30, tzinfo=timezone.utc),
            is_read=False,
        ),
    ]


# ── No credentials ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_handle_command_no_credentials(agent, db_session):
    with patch.object(agent, "_get_provider_and_credential", return_value=(None, None)):
        result = await agent.handle_command(
            db_session, uuid.uuid4(), "email_read", "check my emails"
        )
    assert "not connected" in result.lower()
    assert "gmail" in result.lower()


# ── email_read ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_read_empty_inbox(agent, db_session, mock_ollama):
    mock_provider = MagicMock()
    mock_provider.get_unread = AsyncMock(return_value=[])
    mock_provider.token_refreshed = False

    with patch.object(agent, "_get_provider_and_credential", return_value=(mock_provider, MagicMock())):
        with patch.object(agent, "_sync_tokens", new_callable=AsyncMock):
            result = await agent.handle_command(
                db_session, uuid.uuid4(), "email_read", "check emails"
            )

    assert "inbox clear" in result.lower() or "no unread" in result.lower()
    mock_ollama.chat.assert_not_called()


@pytest.mark.asyncio
async def test_read_with_messages(agent, db_session, mock_ollama, sample_messages):
    mock_provider = MagicMock()
    mock_provider.get_unread = AsyncMock(return_value=sample_messages)
    mock_provider.token_refreshed = False

    mock_ollama.chat.return_value = {
        "content": "1. Alice: Q3 Report 🟡\n2. Bob: Lunch 🟢",
        "model": "test",
        "tokens_used": 50,
    }

    with patch.object(agent, "_get_provider_and_credential", return_value=(mock_provider, MagicMock())):
        with patch.object(agent, "_sync_tokens", new_callable=AsyncMock):
            result = await agent.handle_command(
                db_session, uuid.uuid4(), "email_read", "check emails"
            )

    assert "Unread Emails (2)" in result


# ── email_send ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_without_email_address(agent, db_session, mock_ollama):
    mock_provider = MagicMock()
    mock_provider.token_refreshed = False

    mock_ollama.chat.return_value = {
        "content": '{"action":"send","recipient":"John","subject":null,"content":"hi","email_ref":null}',
        "model": "test", "tokens_used": 10,
    }

    with patch.object(agent, "_get_provider_and_credential", return_value=(mock_provider, MagicMock())):
        with patch.object(agent, "_sync_tokens", new_callable=AsyncMock):
            result = await agent.handle_command(
                db_session, uuid.uuid4(), "email_send", "send email to John saying hi"
            )

    assert "valid email address" in result.lower()
    mock_provider.send.assert_not_called()


@pytest.mark.asyncio
async def test_send_with_valid_address(agent, db_session, mock_ollama):
    mock_provider = MagicMock()
    mock_provider.send = AsyncMock(return_value="msg_123")
    mock_provider.token_refreshed = False

    mock_ollama.chat.return_value = {
        "content": '{"action":"send","recipient":"john@example.com","subject":"Hello","content":"I will be there at 3pm.","email_ref":null}',
        "model": "test", "tokens_used": 10,
    }

    with patch.object(agent, "_get_provider_and_credential", return_value=(mock_provider, MagicMock())):
        with patch.object(agent, "_sync_tokens", new_callable=AsyncMock):
            result = await agent.handle_command(
                db_session, uuid.uuid4(), "email_send",
                "send email to john@example.com I'll be there at 3pm",
            )

    assert "john@example.com" in result
    assert "sent" in result.lower()
    mock_provider.send.assert_called_once()


# ── email_draft ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_draft_without_thread(agent, db_session, mock_ollama):
    mock_provider = MagicMock()
    mock_provider.get_unread = AsyncMock(return_value=[])
    mock_provider.token_refreshed = False

    parse_response = '{"action":"draft","recipient":"alice@example.com","subject":"Re: Q3","content":"Looks good","email_ref":null}'
    draft_response = "Thank you for sending the Q3 report. It looks good overall."

    call_count = 0

    async def _chat_mock(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"content": parse_response, "model": "test", "tokens_used": 10}
        return {"content": draft_response, "model": "test", "tokens_used": 50}

    mock_ollama.chat = _chat_mock

    with patch.object(agent, "_get_provider_and_credential", return_value=(mock_provider, MagicMock())):
        with patch.object(agent, "_sync_tokens", new_callable=AsyncMock):
            result = await agent.handle_command(
                db_session, uuid.uuid4(), "email_draft", "draft reply to Alice saying looks good"
            )

    assert "Draft ready" in result
    assert "alice@example.com" in result


# ── token sync ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_tokens_updates_credential_on_refresh(agent, db_session, mock_settings):
    cred = MagicMock()
    cred.access_token_enc = "old"
    cred.refresh_token_enc = None
    cred.token_expiry = None

    provider = MagicMock()
    provider.token_refreshed = True
    provider.new_access_token = "new-access-token"
    provider.new_refresh_token = None
    provider.new_token_expiry = datetime(2026, 7, 1, tzinfo=timezone.utc)

    with patch("app.agents.email_agent.encrypt_token", return_value="encrypted-new"):
        await agent._sync_tokens(db_session, cred, provider)

    assert cred.access_token_enc == "encrypted-new"


@pytest.mark.asyncio
async def test_sync_tokens_skips_when_not_refreshed(agent, db_session):
    cred = MagicMock()
    provider = MagicMock()
    provider.token_refreshed = False

    original_enc = cred.access_token_enc
    await agent._sync_tokens(db_session, cred, provider)
    # cred.access_token_enc should be unchanged
    assert cred.access_token_enc == original_enc


# ── error handling ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_provider_error_returns_friendly_message(agent, db_session):
    mock_provider = MagicMock()
    mock_provider.get_unread = AsyncMock(side_effect=RuntimeError("API rate limit exceeded"))
    mock_provider.token_refreshed = False

    with patch.object(agent, "_get_provider_and_credential", return_value=(mock_provider, MagicMock())):
        with patch.object(agent, "_sync_tokens", new_callable=AsyncMock):
            result = await agent.handle_command(
                db_session, uuid.uuid4(), "email_read", "check emails"
            )

    assert "error" in result.lower() or "⚠️" in result
