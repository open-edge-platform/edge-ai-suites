# api/v1/api.py
from fastapi import APIRouter
from api.v1.endpoints import system, object, task

api_router = APIRouter()

api_router.include_router(system.router, prefix="/system", tags=["System"])
api_router.include_router(object.router, prefix="/object", tags=["EDU-AI Process"])
api_router.include_router(task.router, prefix="/task", tags=["EDU-AI Task"])

