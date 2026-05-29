import uuid

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, Database
from app.models.db.conversation import Conversation
from app.models.db.message import Message
from app.models.schemas.message import (
    ConversationResponse,
    MessageResponse,
    PaginatedConversations,
    PaginatedMessages,
)

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/conversations", response_model=PaginatedConversations)
async def list_conversations(
    current_user: CurrentUser,
    db: Database,
    status: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> PaginatedConversations:
    stmt = select(Conversation).where(Conversation.user_id == current_user.id)
    if status:
        stmt = stmt.where(Conversation.status == status)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Conversation.updated_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    items = list(result.scalars().all())

    return PaginatedConversations(
        items=[ConversationResponse.model_validate(c) for c in items],
        total=total,
    )


@router.get("/conversations/{conversation_id}", response_model=PaginatedMessages)
async def get_conversation_messages(
    conversation_id: uuid.UUID,
    current_user: CurrentUser,
    db: Database,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> PaginatedMessages:
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conversation = conv_result.scalar_one_or_none()
    if not conversation:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Conversation not found")

    count_stmt = select(func.count(Message.id)).where(
        Message.conversation_id == conversation_id
    )
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    items = list(result.scalars().all())

    return PaginatedMessages(
        items=[MessageResponse.model_validate(m) for m in items],
        total=total,
        page=offset // limit + 1,
        size=limit,
    )
