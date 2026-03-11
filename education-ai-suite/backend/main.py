# main.py
import uvicorn
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import engine, get_db, Base
from api.route import router as api_router

import sys
from core.checks import check_services

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Edu-AI Orchestrator")

app.include_router(api_router, prefix="/api")

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}

if __name__ == "__main__":
    if not check_services():
        print("Redis or PostgreSQL not ready")
        sys.exit(1)
    # develop on Windows recommand reload
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)