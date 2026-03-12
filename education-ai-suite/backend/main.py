# main.py
import uvicorn, sys
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import engine, get_db, Base
from api.v1.api import api_router
from core.checks import check_services
from core.exceptions import setup_exception_handlers

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Edu-AI Orchestrator")
setup_exception_handlers(app)
# app.include_router(api_router, prefix="/api")
app.include_router(api_router, prefix="/api/v1", tags=["EDU AI Tasks"])

if __name__ == "__main__":
    if not check_services():
        print("Redis or PostgreSQL not ready")
        sys.exit(1)
    # develop on Windows recommand reload
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)