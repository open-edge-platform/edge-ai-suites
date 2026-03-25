# api/v1/api.py
from fastapi import APIRouter
from api.v1.endpoints import system, media, task, test

api_router = APIRouter()

api_router.include_router(system.router, prefix="/system", tags=["System"])
api_router.include_router(media.router, prefix="/media", tags=["EDU-AI Media Process"])
api_router.include_router(task.router, prefix="/task", tags=["EDU-AI Task"])

api_router.include_router(test.router, prefix="/test", tags=["For test"])
