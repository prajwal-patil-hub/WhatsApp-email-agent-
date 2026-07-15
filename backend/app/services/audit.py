import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.db.audit import AuditLog

logger = get_logger(__name__)


async def log_action(
    db: AsyncSession,
    action: str,
    *,
    user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    status: str = "success",
    details: dict[str, Any] | None = None,
    duration_ms: int | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        status=status,
        details=details or {},
        duration_ms=duration_ms,
        ip_address=ip_address,
    )
    db.add(entry)
    await db.flush()
    logger.info(
        "audit",
        action=action,
        user_id=str(user_id) if user_id else None,
        resource_type=resource_type,
        resource_id=resource_id,
        status=status,
    )
    return entry
