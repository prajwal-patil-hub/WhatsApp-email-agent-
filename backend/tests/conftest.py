import asyncio
import json
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models.db import Base

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def mock_settings(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test_secret_key_32_chars_minimum!")
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("WHATSAPP_API_TOKEN", "test_wa_token")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "123456789")
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "test_verify_token")
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "test_app_secret")
    monkeypatch.setenv("ADMIN_PHONE_NUMBER", "14155551234")
    monkeypatch.setenv("ADMIN_SECRET", "test_admin_secret")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/1")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def mock_ollama():
    with patch("app.services.ollama.OllamaService") as mock_cls:
        instance = mock_cls.return_value
        instance.chat = AsyncMock(return_value={
            "content": "Hello! I'm your AI Chief of Staff. How can I help you today?",
            "model": "qwen3:latest",
            "tokens_used": 42,
        })
        instance.is_available = AsyncMock(return_value=True)
        instance.list_models = AsyncMock(return_value=["qwen3:latest", "mistral:latest"])
        yield instance


@pytest.fixture
def mock_redis():
    with patch("app.memory.short_term._get_redis") as mock_fn:
        redis = MagicMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock(return_value=True)
        redis.delete = AsyncMock(return_value=1)
        redis.ping = AsyncMock(return_value=True)
        mock_fn.return_value = redis
        yield redis


@pytest.fixture
def mock_whatsapp():
    with patch("app.services.whatsapp.WhatsAppService") as mock_cls:
        instance = mock_cls.return_value
        instance.send_text = AsyncMock(return_value={"messages": [{"id": "wamid.test123"}]})
        instance.get_media_url = AsyncMock(return_value="https://example.com/media/test.ogg")
        instance.download_media = AsyncMock(return_value=b"fake_audio_bytes")
        yield instance


@pytest.fixture
def whatsapp_text_payload():
    with open("tests/fixtures/whatsapp_messages.json") as f:
        fixtures = json.load(f)
    return fixtures["text_message"]


@pytest.fixture
def whatsapp_voice_payload():
    with open("tests/fixtures/whatsapp_messages.json") as f:
        fixtures = json.load(f)
    return fixtures["voice_message"]


@pytest.fixture
def sample_user_id():
    return uuid.uuid4()


@pytest.fixture
def sample_conversation_id():
    return uuid.uuid4()
