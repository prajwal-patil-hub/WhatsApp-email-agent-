"""
Long-term memory: PostgreSQL + Qdrant for persistent, semantically-searchable memories.

Each memory has:
- A PostgreSQL record with structured metadata
- A Qdrant vector point for semantic similarity search

Phase 1: PostgreSQL storage only (Qdrant search activated in Phase 4).
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
    embed: bool = False,
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
    """Phase 1: filter-only search. Phase 4: semantic search via Qdrant."""
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


async def _store_embedding(memory: Memory) -> None:
    """Store vector in Qdrant. Activated in Phase 4 when knowledge base is built."""
    try:
        from app.services.ollama import get_ollama_service
        from qdrant_client import QdrantClient
        from qdrant_client.models import PointStruct

        settings = get_settings()
        ollama = get_ollama_service()
        vector = await ollama.embed(memory.content)

        client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
        point_id = str(uuid.uuid4())
        client.upsert(
            collection_name=settings.QDRANT_MEMORY_COLLECTION,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "memory_id": str(memory.id),
                        "user_id": str(memory.user_id),
                        "memory_type": memory.memory_type,
                        "summary": memory.summary,
                    },
                )
            ],
        )
        memory.embedding_id = point_id
    except Exception as exc:
        logger.warning("embedding_store_failed", error=str(exc), memory_id=str(memory.id))


async def _delete_embedding(embedding_id: str) -> None:
    try:
        from qdrant_client import QdrantClient

        settings = get_settings()
        client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
        client.delete(
            collection_name=settings.QDRANT_MEMORY_COLLECTION,
            points_selector=[embedding_id],
        )
    except Exception as exc:
        logger.warning("embedding_delete_failed", error=str(exc), embedding_id=embedding_id)
