"""Briefing route — Phase 7. Consumed by WhatsApp intent + n8n morning workflow."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentUser, Database
from app.services import audit
from app.services.briefing import build_briefing

router = APIRouter(prefix="/briefing", tags=["briefing"])


class BriefingResponse(BaseModel):
    briefing: str


@router.get("", response_model=BriefingResponse)
async def get_briefing(current_user: CurrentUser, db: Database) -> BriefingResponse:
    text = await build_briefing(db, current_user.id)
    await audit.log_action(db, action="briefing.generated", user_id=current_user.id)
    return BriefingResponse(briefing=text)
