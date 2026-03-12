# api/v1/api.py
from fastapi import APIRouter
from api.v1.endpoints import tasks, health

api_router = APIRouter()

api_router.include_router(tasks.router, prefix="/tasks", tags=["Video Tasks"])
api_router.include_router(health.router, prefix="/system", tags=["System"])
