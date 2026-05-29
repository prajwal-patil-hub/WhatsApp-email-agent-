import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, Database
from app.memory.long_term import delete_memory, search_memories, store_memory
from app.models.db.memory import Memory
from app.models.schemas.memory import (
    MemoryCreate,
    MemoryResponse,
    MemoryUpdate,
    PaginatedMemories,
)

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("", response_model=PaginatedMemories)
async def list_memories(
    current_user: CurrentUser,
    db: Database,
    memory_type: str | None = Query(None),
    query: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedMemories:
    memories = await search_memories(
        db,
        user_id=current_user.id,
        query=query,
        memory_type=memory_type,
        limit=limit,
    )
    count_stmt = select(func.count(Memory.id)).where(Memory.user_id == current_user.id)
    if memory_type:
        count_stmt = count_stmt.where(Memory.memory_type == memory_type)
    total = (await db.execute(count_stmt)).scalar_one()

    return PaginatedMemories(
        items=[MemoryResponse.model_validate(m) for m in memories],
        total=total,
    )


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def create_memory(
    payload: MemoryCreate,
    current_user: CurrentUser,
    db: Database,
) -> MemoryResponse:
    memory = await store_memory(
        db,
        user_id=current_user.id,
        memory_type=payload.memory_type,
        content=payload.content,
        summary=payload.summary,
        importance=payload.importance,
        source=payload.source or "api",
        embed=False,
    )
    await db.commit()
    return MemoryResponse.model_validate(memory)


@router.put("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: uuid.UUID,
    payload: MemoryUpdate,
    current_user: CurrentUser,
    db: Database,
) -> MemoryResponse:
    result = await db.execute(
        select(Memory).where(Memory.id == memory_id, Memory.user_id == current_user.id)
    )
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    if payload.content is not None:
        memory.content = payload.content
    if payload.summary is not None:
        memory.summary = payload.summary
    if payload.importance is not None:
        memory.importance = payload.importance
    if payload.expires_at is not None:
        memory.expires_at = payload.expires_at

    await db.commit()
    return MemoryResponse.model_validate(memory)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_memory(
    memory_id: uuid.UUID,
    current_user: CurrentUser,
    db: Database,
) -> None:
    deleted = await delete_memory(db, memory_id=memory_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    await db.commit()
