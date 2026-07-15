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

_TEST_ENV = {
    "SECRET_KEY": "test_secret_key_32_chars_minimum!",
    "DATABASE_URL": TEST_DATABASE_URL,
    "WHATSAPP_API_TOKEN": "test_wa_token",
    "WHATSAPP_PHONE_NUMBER_ID": "123456789",
    "WHATSAPP_VERIFY_TOKEN": "test_verify_token",
    "WHATSAPP_APP_SECRET": "test_app_secret",
    "ADMIN_PHONE_NUMBER": "14155551234",
    "ADMIN_SECRET": "test_admin_secret",
    "REDIS_URL": "redis://localhost:6379/1",
}


@pytest.fixture(autouse=True)
def _base_test_env(monkeypatch):
    """Every test gets valid required settings so get_settings() never explodes."""
    for key, value in _TEST_ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_engine():
    from sqlalchemy.pool import StaticPool

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
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


# ── Integration test fixtures ─────────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_user(db_session):
    """A persisted admin user for integration tests (get-or-create)."""
    from sqlalchemy import select

    from app.models.db.user import User

    result = await db_session.execute(
        select(User).where(User.phone_number == "14155551234")
    )
    user = result.scalar_one_or_none()
    if user is None:
        user = User(phone_number="14155551234", role="admin")
        db_session.add(user)
        await db_session.flush()
    return user


@pytest_asyncio.fixture
async def auth_headers(db_session, test_user):
    """Valid JWT auth headers backed by a non-revoked Session record."""
    from datetime import timezone

    from app.core.security import create_access_token, decode_token
    from app.models.db.session import Session

    token = create_access_token(str(test_user.id), role=test_user.role)
    decoded = decode_token(token)
    import datetime as dt

    db_session.add(
        Session(
            user_id=test_user.id,
            token_jti=decoded["jti"],
            expires_at=dt.datetime.fromtimestamp(decoded["exp"], tz=timezone.utc),
        )
    )
    await db_session.flush()
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def client(mock_settings, test_engine, db_session):
    """Full-stack AsyncClient with DB dependency overridden to use test session."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from httpx import ASGITransport, AsyncClient

    from app.core.database import get_db

    async def _override_db():
        yield db_session

    with (
        patch("app.core.database.create_tables", new_callable=AsyncMock),
        patch("app.services.whisper.warmup_whisper"),
        patch("app.services.ollama.OllamaService.is_available", new_callable=AsyncMock, return_value=True),
    ):
        from app.main import create_app

        app = create_app()
        app.dependency_overrides[get_db] = _override_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c

        app.dependency_overrides.clear()
