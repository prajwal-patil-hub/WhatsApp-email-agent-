"""
Long-term memory: PostgreSQL + Qdrant for persistent, semantically-searchable memories.

Each memory has:
- A PostgreSQL record with structured metadata
- A Qdrant vector point for semantic similarity search

Phase 4: Qdrant semantic search active, PostgreSQL remains source of truth.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.db.memory import Memory

logger = get_logger(__name__)


async def store_memory(
    db: AsyncSession,
    user_id: uuid.UUID,
    memory_type: str,
    content: str,
    summary: str | None = None,
    importance: float = 0.5,
    source: str | None = None,
    embed: bool = True,
) -> Memory:
    memory = Memory(
        user_id=user_id,
        memory_type=memory_type,
        content=content,
        summary=summary or content[:200],
        importance=importance,
        source=source,
    )
    db.add(memory)
    await db.flush()

    if embed:
        await _store_embedding(memory)

    logger.info(
        "long_term_memory_stored",
        memory_id=str(memory.id),
        memory_type=memory_type,
        user_id=str(user_id),
    )
    return memory


async def search_memories(
    db: AsyncSession,
    user_id: uuid.UUID,
    query: str | None = None,
    memory_type: str | None = None,
    limit: int = 10,
) -> list[Memory]:
    """Semantic search via Qdrant (Phase 4), falling back to PG filter search."""
    if query:
        semantic = await _semantic_search(db, user_id, query, memory_type, limit)
        if semantic is not None:
            return semantic

    now = datetime.now(timezone.utc)
    stmt = (
        select(Memory)
        .where(
            Memory.user_id == user_id,
            (Memory.expires_at == None) | (Memory.expires_at > now),  # noqa: E711
        )
        .order_by(Memory.importance.desc(), Memory.access_count.desc())
        .limit(limit)
    )
    if memory_type:
        stmt = stmt.where(Memory.memory_type == memory_type)

    result = await db.execute(stmt)
    memories = list(result.scalars().all())

    if query and memories:
        query_lower = query.lower()
        memories.sort(
            key=lambda m: query_lower in m.content.lower(), reverse=True
        )

    return memories


async def delete_memory(
    db: AsyncSession, memory_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    result = await db.execute(
        select(Memory).where(Memory.id == memory_id, Memory.user_id == user_id)
    )
    memory = result.scalar_one_or_none()
    if not memory:
        return False
    await db.delete(memory)
    if memory.embedding_id:
        await _delete_embedding(memory.embedding_id)
    return True


async def _semantic_search(
    db: AsyncSession,
    user_id: uuid.UUID,
    query: str,
    memory_type: str | None,
    limit: int,
) -> list[Memory] | None:
    """Returns None when Qdrant/Ollama are unavailable so callers can fall back."""
    try:
        from app.services.ollama import get_ollama_service
        from app.services.qdrant import get_qdrant_service

        settings = get_settings()
        vector = await get_ollama_service().embed(query)
        hits = await get_qdrant_service().search(
            collection=settings.QDRANT_MEMORY_COLLECTION,
            vector=vector,
            user_id=str(user_id),
            limit=limit,
        )
    except Exception as exc:
        logger.warning("semantic_search_unavailable", error=str(exc))
        return None

    if not hits:
        return []

    memory_ids = [uuid.UUID(h["memory_id"]) for h in hits if h.get("memory_id")]
    if not memory_ids:
        return []

    now = datetime.now(timezone.utc)
    stmt = select(Memory).where(
        Memory.id.in_(memory_ids),
        Memory.user_id == user_id,
        (Memory.expires_at == None) | (Memory.expires_at > now),  # noqa: E711
    )
    if memory_type:
        stmt = stmt.where(Memory.memory_type == memory_type)
    result = await db.execute(stmt)
    by_id = {m.id: m for m in result.scalars().all()}
    # Preserve Qdrant relevance order
    return [by_id[mid] for mid in memory_ids if mid in by_id]


async def _store_embedding(memory: Memory) -> None:
    """Store vector in Qdrant. Activated in Phase 4 when knowledge base is built."""
    try:
        from app.services.ollama import get_ollama_service
        from app.services.qdrant import get_qdrant_service

        settings = get_settings()
        vector = await get_ollama_service().embed(memory.content)
        point_id = await get_qdrant_service().upsert(
            collection=settings.QDRANT_MEMORY_COLLECTION,
            vector=vector,
            payload={
                "memory_id": str(memory.id),
                "user_id": str(memory.user_id),
                "memory_type": memory.memory_type,
                "summary": memory.summary,
            },
        )
        memory.embedding_id = point_id
    except Exception as exc:
        logger.warning("embedding_store_failed", error=str(exc), memory_id=str(memory.id))


async def _delete_embedding(embedding_id: str) -> None:
    try:
        from app.services.qdrant import get_qdrant_service

        settings = get_settings()
        await get_qdrant_service().delete_points(
            settings.QDRANT_MEMORY_COLLECTION, [embedding_id]
        )
    except Exception as exc:
        logger.warning("embedding_delete_failed", error=str(exc), embedding_id=embedding_id)
