from fastapi import APIRouter

from app.api.routes import auth, health, memory, messages, whatsapp

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(whatsapp.router)
api_router.include_router(messages.router)
api_router.include_router(memory.router)
