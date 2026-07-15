"""Research routes — Phase 5."""

import uuid

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.agents.research_agent import ResearchAgent
from app.api.deps import CurrentUser, Database, OllamaClient
from app.models.db.knowledge import KnowledgeItem

router = APIRouter(prefix="/research", tags=["research"])


class ResearchRequest(BaseModel):
    question: str


class ResearchResponse(BaseModel):
    report: str


class ReportSummary(BaseModel):
    id: uuid.UUID
    title: str | None
    status: str

    model_config = {"from_attributes": True}


class ReportListResponse(BaseModel):
    items: list[ReportSummary]
    total: int


@router.post("", response_model=ResearchResponse)
async def run_research(
    payload: ResearchRequest,
    current_user: CurrentUser,
    db: Database,
    ollama: OllamaClient,
) -> ResearchResponse:
    agent = ResearchAgent(ollama=ollama)
    report = await agent.handle_command(db, current_user.id, "research", payload.question)
    return ResearchResponse(report=report)


@router.get("/reports", response_model=ReportListResponse)
async def list_reports(
    current_user: CurrentUser,
    db: Database,
    limit: int = Query(default=20, ge=1, le=100),
) -> ReportListResponse:
    result = await db.execute(
        select(KnowledgeItem)
        .where(
            KnowledgeItem.user_id == current_user.id,
            KnowledgeItem.source_type == "research",
        )
        .order_by(KnowledgeItem.created_at.desc())
        .limit(limit)
    )
    items = list(result.scalars().all())
    return ReportListResponse(
        items=[ReportSummary.model_validate(i) for i in items], total=len(items)
    )
