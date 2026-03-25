from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
from services.storage_service import storage_service
import time

router = APIRouter()

@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    status = {
        "status": "healthy",
        "timestamp": time.time(),
        "services": {
            "postgres": "unknown",
            "minio": "unknown"
        }
    }

    # PostgreSQL
    try:
        db.execute(text("SELECT 1"))
        status["services"]["postgres"] = "online"
    except Exception as e:
        status["services"]["postgres"] = f"offline: {str(e)}"
        status["status"] = "unhealthy"

    # minIO
    if hasattr(storage_service, "_store") and storage_service._store:
        try:
            storage_service._store.list_buckets()
            status["services"]["minio"] = "online"
        except Exception as e:
            status["services"]["minio"] = f"connection error: {str(e)}"
            status["status"] = "unhealthy"
    else:
        err = getattr(storage_service, "_error_msg", "Not initialized")
        status["services"]["minio"] = f"offline: {err}"
        status["status"] = "unhealthy"

    return status