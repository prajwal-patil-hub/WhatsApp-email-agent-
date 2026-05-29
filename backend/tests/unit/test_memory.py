"""Unit tests for the 3-layer memory system."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.memory import short_term


class TestShortTermMemory:
    @pytest.mark.asyncio
    async def test_add_and_get_message(self):
        conversation_id = uuid.uuid4()
        stored_data = {}

        async def mock_get(key):
            return stored_data.get(key)

        async def mock_setex(key, ttl, value):
            stored_data[key] = value

        mock_redis = MagicMock()
        mock_redis.get = mock_get
        mock_redis.setex = mock_setex

        with patch("app.memory.short_term._get_redis", return_value=mock_redis):
            await short_term.add_message(conversation_id, "user", "Hello")
            context = await short_term.get_context(conversation_id)

        assert len(context) == 1
        assert context[0]["role"] == "user"
        assert context[0]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_context_trimmed_when_exceeds_max(self):
        conversation_id = uuid.uuid4()
        stored_data = {}

        async def mock_get(key):
            return stored_data.get(key)

        async def mock_setex(key, ttl, value):
            stored_data[key] = value

        mock_redis = MagicMock()
        mock_redis.get = mock_get
        mock_redis.setex = mock_setex

        with patch("app.memory.short_term._get_redis", return_value=mock_redis), \
             patch("app.core.config.get_settings") as mock_settings:
            settings = MagicMock()
            settings.REDIS_CONTEXT_MAX_MESSAGES = 4
            settings.REDIS_CONTEXT_TTL = 86400
            mock_settings.return_value = settings

            for i in range(6):
                await short_term.add_message(conversation_id, "user", f"Message {i}")

            context = await short_term.get_context(conversation_id)
            assert len(context) <= 4

    @pytest.mark.asyncio
    async def test_clear_context(self):
        conversation_id = uuid.uuid4()
        mock_redis = MagicMock()
        mock_redis.delete = AsyncMock(return_value=1)

        with patch("app.memory.short_term._get_redis", return_value=mock_redis):
            await short_term.clear_context(conversation_id)

        mock_redis.delete.assert_called_once_with(f"conversation:{conversation_id}:context")

    @pytest.mark.asyncio
    async def test_get_context_empty_returns_empty_list(self):
        conversation_id = uuid.uuid4()
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch("app.memory.short_term._get_redis", return_value=mock_redis):
            context = await short_term.get_context(conversation_id)

        assert context == []

    @pytest.mark.asyncio
    async def test_ping_success(self):
        mock_redis = MagicMock()
        mock_redis.ping = AsyncMock(return_value=True)

        with patch("app.memory.short_term._get_redis", return_value=mock_redis):
            result = await short_term.ping()

        assert result is True

    @pytest.mark.asyncio
    async def test_ping_failure(self):
        mock_redis = MagicMock()
        mock_redis.ping = AsyncMock(side_effect=Exception("Connection refused"))

        with patch("app.memory.short_term._get_redis", return_value=mock_redis):
            result = await short_term.ping()

        assert result is False


class TestLongTermMemory:
    @pytest.mark.asyncio
    async def test_store_memory(self, db_session, sample_user_id):
        from app.memory.long_term import store_memory
        from app.models.db.user import User

        user = User(
            id=sample_user_id,
            phone_number=f"+1{str(sample_user_id.int)[:10]}",
        )
        db_session.add(user)
        await db_session.flush()

        memory = await store_memory(
            db_session,
            user_id=sample_user_id,
            memory_type="preference",
            content="I prefer concise responses",
            importance=0.8,
        )
        assert memory.id is not None
        assert memory.memory_type == "preference"
        assert memory.importance == 0.8
        assert memory.content == "I prefer concise responses"

    @pytest.mark.asyncio
    async def test_search_memories_by_type(self, db_session, sample_user_id):
        from app.memory.long_term import search_memories, store_memory
        from app.models.db.user import User

        user = User(
            id=sample_user_id,
            phone_number=f"+2{str(sample_user_id.int)[:10]}",
        )
        db_session.add(user)
        await db_session.flush()

        await store_memory(db_session, user_id=sample_user_id, memory_type="preference", content="Prefers morning meetings")
        await store_memory(db_session, user_id=sample_user_id, memory_type="fact", content="Lives in New York")

        preferences = await search_memories(db_session, user_id=sample_user_id, memory_type="preference")
        assert len(preferences) >= 1
        assert all(m.memory_type == "preference" for m in preferences)

    @pytest.mark.asyncio
    async def test_delete_memory(self, db_session, sample_user_id):
        from app.memory.long_term import delete_memory, store_memory
        from app.models.db.user import User

        user = User(
            id=sample_user_id,
            phone_number=f"+3{str(sample_user_id.int)[:10]}",
        )
        db_session.add(user)
        await db_session.flush()

        memory = await store_memory(
            db_session,
            user_id=sample_user_id,
            memory_type="fact",
            content="To be deleted",
        )
        await db_session.flush()

        deleted = await delete_memory(db_session, memory_id=memory.id, user_id=sample_user_id)
        assert deleted is True

    @pytest.mark.asyncio
    async def test_delete_nonexistent_memory_returns_false(self, db_session, sample_user_id):
        from app.memory.long_term import delete_memory
        deleted = await delete_memory(db_session, memory_id=uuid.uuid4(), user_id=sample_user_id)
        assert deleted is False
