from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import create_tables, dispose_engine
from app.core.logging import get_logger, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging()
    logger = get_logger("startup")

    logger.info("starting_up", app=settings.APP_NAME, env=settings.ENVIRONMENT)

    # Validate all required environment variables before accepting requests
    settings.validate_required()
    logger.info("config_validated")

    # Initialize database tables (Alembic handles schema in production)
    await create_tables()
    logger.info("database_ready")

    # Warm up Whisper model off the event loop (non-fatal if it fails)
    if not settings.is_development:
        import asyncio
        from app.services.whisper import warmup_whisper

        await asyncio.get_event_loop().run_in_executor(None, warmup_whisper)

    # Bootstrap Qdrant vector collections (non-fatal — semantic search degrades gracefully)
    try:
        from app.services.qdrant import get_qdrant_service

        await get_qdrant_service().ensure_collections()
        logger.info("qdrant_ready")
    except Exception as exc:
        logger.warning("qdrant_unavailable", error=str(exc))

    logger.info("startup_complete", phase=4)
    yield

    logger.info("shutting_down")
    from app.memory.short_term import close as redis_close

    await redis_close()
    await dispose_engine()
    logger.info("shutdown_complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        description="Personal AI Chief of Staff — API",
        version="1.0.0",
        docs_url="/api/docs" if settings.DEBUG else None,
        redoc_url="/api/redoc" if settings.DEBUG else None,
        openapi_url="/api/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://frontend:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger = get_logger("error_handler")
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            error=str(exc),
            exc_info=exc,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    return app


app = create_app()
