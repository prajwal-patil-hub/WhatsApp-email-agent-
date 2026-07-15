"""
Short-term memory: Redis-based conversation context.

Stores the last N messages of a conversation as a JSON list.
Keys expire after REDIS_CONTEXT_TTL seconds (default 24h).
"""

import asyncio
import json
import uuid
from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis_client: aioredis.Redis | None = None
_redis_lock = asyncio.Lock()


async def _get_redis_async() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        async with _redis_lock:
            if _redis_client is None:
                settings = get_settings()
                _redis_client = aioredis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                )
    return _redis_client


def _get_redis() -> aioredis.Redis:
    """Sync accessor — only safe after _get_redis_async() has been called at least once."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


def _context_key(conversation_id: str | uuid.UUID) -> str:
    return f"conversation:{conversation_id}:context"


async def get_context(conversation_id: str | uuid.UUID) -> list[dict[str, str]]:
    redis = _get_redis()
    raw = await redis.get(_context_key(conversation_id))
    if not raw:
        return []
    return json.loads(raw)


async def add_message(
    conversation_id: str | uuid.UUID,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    settings = get_settings()
    redis = _get_redis()
    key = _context_key(conversation_id)

    messages = await get_context(conversation_id)
    messages.append({"role": role, "content": content})

    if len(messages) > settings.REDIS_CONTEXT_MAX_MESSAGES:
        # Keep system message if present, trim oldest conversation turns
        system_msgs = [m for m in messages if m["role"] == "system"]
        other_msgs = [m for m in messages if m["role"] != "system"]
        other_msgs = other_msgs[-(settings.REDIS_CONTEXT_MAX_MESSAGES - len(system_msgs)):]
        messages = system_msgs + other_msgs

    await redis.setex(
        key,
        settings.REDIS_CONTEXT_TTL,
        json.dumps(messages),
    )


async def clear_context(conversation_id: str | uuid.UUID) -> None:
    redis = _get_redis()
    await redis.delete(_context_key(conversation_id))


async def set_context(
    conversation_id: str | uuid.UUID, messages: list[dict[str, str]]
) -> None:
    settings = get_settings()
    redis = _get_redis()
    await redis.setex(
        _context_key(conversation_id),
        settings.REDIS_CONTEXT_TTL,
        json.dumps(messages),
    )


async def ping() -> bool:
    try:
        redis = _get_redis()
        await redis.ping()
        return True
    except Exception:
        return False


async def close() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
