import time
from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.memory import short_term
from app.services.ollama import get_ollama_service

router = APIRouter(tags=["health"])

_start_time = time.time()


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "app": get_settings().APP_NAME,
        "version": "1.0.0",
        "phase": 1,
        "uptime_seconds": int(time.time() - _start_time),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/ready")
async def readiness() -> dict:
    checks: dict[str, str] = {}

    # PostgreSQL
    try:
        from app.core.database import get_session_factory

        async with get_session_factory()() as db:
            await db.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:
        checks["postgres"] = f"error: {exc}"

    # Redis
    checks["redis"] = "ok" if await short_term.ping() else "error"

    # Ollama
    ollama = get_ollama_service()
    checks["ollama"] = "ok" if await ollama.is_available() else "unavailable"

    all_critical_ok = checks["postgres"] == "ok" and checks["redis"] == "ok"
    status_code = 200 if all_critical_ok else 503

    from fastapi import Response
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if all_critical_ok else "not_ready", "checks": checks},
    )
