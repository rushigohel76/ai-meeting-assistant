from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.meetings import router as meetings_router
from app.api.webhooks import router as webhooks_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(meetings_router)
api_router.include_router(webhooks_router)
api_router.include_router(health_router)
