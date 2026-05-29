"""
Working memory: PostgreSQL-based active project and goal state.

Stores current projects, active goals, and ongoing context with
a retention window of days to weeks.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.db.memory import Memory

logger = get_logger(__name__)

WORKING_MEMORY_TYPES = {"goal", "project", "context"}
WORKING_MEMORY_TTL_DAYS = 30


async def get_working_context(
    db: AsyncSession, user_id: uuid.UUID
) -> list[Memory]:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Memory)
        .where(
            Memory.user_id == user_id,
            Memory.memory_type.in_(WORKING_MEMORY_TYPES),
            (Memory.expires_at == None) | (Memory.expires_at > now),  # noqa: E711
        )
        .order_by(Memory.importance.desc(), Memory.last_accessed.desc())
        .limit(10)
    )
    return list(result.scalars().all())


async def upsert_goal(
    db: AsyncSession,
    user_id: uuid.UUID,
    content: str,
    summary: str | None = None,
    importance: float = 0.7,
) -> Memory:
    ttl = datetime.now(timezone.utc) + timedelta(days=WORKING_MEMORY_TTL_DAYS)
    memory = Memory(
        user_id=user_id,
        memory_type="goal",
        content=content,
        summary=summary or content[:200],
        importance=importance,
        expires_at=ttl,
        source="user",
    )
    db.add(memory)
    await db.flush()
    logger.info("working_memory_goal_created", user_id=str(user_id))
    return memory


async def touch_memories(db: AsyncSession, memory_ids: list[uuid.UUID]) -> None:
    now = datetime.now(timezone.utc)
    await db.execute(
        update(Memory)
        .where(Memory.id.in_(memory_ids))
        .values(
            last_accessed=now,
            access_count=Memory.access_count + 1,
        )
    )
