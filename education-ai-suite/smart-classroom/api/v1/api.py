from fastapi import APIRouter

from api.v1.endpoints import sessions

v1_router = APIRouter()
v1_router.include_router(sessions.router, prefix="/sessions", tags=["Sessions"])
