"""Knowledge base routes — Phase 4."""

import uuid

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select

from app.agents.knowledge_agent import KnowledgeAgent
from app.api.deps import CurrentUser, Database, OllamaClient
from app.models.db.knowledge import KnowledgeItem
from app.services import audit
from app.services.documents import SUPPORTED_EXTENSIONS

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB


class KnowledgeItemResponse(BaseModel):
    id: uuid.UUID
    title: str | None
    source_type: str
    status: str
    chunk_count: int

    model_config = {"from_attributes": True}


class KnowledgeListResponse(BaseModel):
    items: list[KnowledgeItemResponse]
    total: int


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str


@router.get("", response_model=KnowledgeListResponse)
async def list_items(
    current_user: CurrentUser,
    db: Database,
    limit: int = Query(default=50, ge=1, le=200),
) -> KnowledgeListResponse:
    result = await db.execute(
        select(KnowledgeItem)
        .where(KnowledgeItem.user_id == current_user.id)
        .order_by(KnowledgeItem.created_at.desc())
        .limit(limit)
    )
    items = list(result.scalars().all())
    return KnowledgeListResponse(
        items=[KnowledgeItemResponse.model_validate(i) for i in items],
        total=len(items),
    )


@router.post("/upload", response_model=KnowledgeItemResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    current_user: CurrentUser,
    db: Database,
    ollama: OllamaClient,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
) -> KnowledgeItemResponse:
    filename = file.filename or "upload.txt"
    if not filename.lower().endswith(SUPPORTED_EXTENSIONS):
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type. Supported: {', '.join(SUPPORTED_EXTENSIONS)}",
        )
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 20 MB)")

    agent = KnowledgeAgent(ollama=ollama)
    await agent.ingest_document(db, current_user.id, data=data, filename=filename, title=title)

    result = await db.execute(
        select(KnowledgeItem)
        .where(KnowledgeItem.user_id == current_user.id)
        .order_by(KnowledgeItem.created_at.desc())
        .limit(1)
    )
    item = result.scalar_one()
    return KnowledgeItemResponse.model_validate(item)


@router.post("/ask", response_model=AskResponse)
async def ask(
    payload: AskRequest,
    current_user: CurrentUser,
    db: Database,
    ollama: OllamaClient,
) -> AskResponse:
    agent = KnowledgeAgent(ollama=ollama)
    answer = await agent.answer(db, current_user.id, payload.question)
    return AskResponse(answer=answer)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: uuid.UUID,
    current_user: CurrentUser,
    db: Database,
) -> None:
    result = await db.execute(
        select(KnowledgeItem).where(
            KnowledgeItem.id == item_id, KnowledgeItem.user_id == current_user.id
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found")

    from app.core.config import get_settings
    from app.services.qdrant import get_qdrant_service

    try:
        await get_qdrant_service().delete_by_filter(
            get_settings().QDRANT_KNOWLEDGE_COLLECTION,
            key="knowledge_item_id",
            value=str(item.id),
        )
    except Exception:
        pass  # Qdrant cleanup is best-effort; PG row is source of truth

    await db.delete(item)
    await audit.log_action(
        db, action="knowledge.delete", user_id=current_user.id,
        resource_type="knowledge_item", resource_id=str(item_id),
    )
