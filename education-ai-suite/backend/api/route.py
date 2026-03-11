# api/route.py
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from core.models import AITask

from processor import run_dummy_ai_logic
from services.storage_service import storage_service

import redis
import json

router = APIRouter()

# Initialize sync Redis client (tporadowski/redis default port 6379)
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

@router.post("/tasks/video-summary")
async def submit_video_task(payload: dict, db: Session = Depends(get_db)):
    # Whether to enable synchronous wait mode (default False, async)
    is_sync = payload.get("sync", False)
    callback_url = payload.get("callback_url")

    # 1. Persist to PostgreSQL regardless of sync/async
    new_task = AITask(
        task_type="video_summary",
        payload=payload,
        status="PENDING",
        user_id="admin"
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    if is_sync:
        # --- Case A: synchronous mode ---
        try:
            # Update status to PROCESSING
            new_task.status = "PROCESSING"
            db.commit()

            # Simulate worker processing (or call the real AI function)
            # Note: dummy_ai_work should be an async function
            result = await run_dummy_ai_logic(payload.get("video_url"))

            # Write back result
            new_task.status = "COMPLETED"
            new_task.result = result
            db.commit()

            return {
                "task_id": new_task.id, 
                "status": "COMPLETED", 
                "result": result,
                "mode": "synchronous"
            }
        except Exception as e:
            new_task.status = "FAILED"
            db.commit()
            raise HTTPException(status_code=500, detail=f"Sync processing failed: {str(e)}")

    else:
        # --- Case B: async callback mode (original logic) ---
        try:
            new_task.status = "QUEUED"
            db.commit()
            
            redis_client.xadd(
                "stream:video_processing",
                {"task_id": str(new_task.id)}
            )
            return {
                "task_id": new_task.id, 
                "status": "QUEUED",
                "mode": "asynchronous",
                "callback_notified": "pending" if callback_url else "none"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Redis error: {str(e)}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str, db: Session = Depends(get_db)):
    # Look up task in the database
    task = db.query(AITask).filter(AITask.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "task_id": task.id,
        "status": task.status,
        "payload": task.payload,
        "result": task.result, # Null if not completed; otherwise the mock summary
        "created_at": task.created_at
    }

@router.post("/tasks/video-upload")
async def submit_upload_task(
    video_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    File-upload task endpoint:
    1. Video stream -> MinIO (via symlink module)
    2. Path -> PostgreSQL
    3. Task ID -> Redis Stream
    """
    try:
        # 1. Call service to handle storage
        minio_payload = await storage_service.upload_and_prepare_payload(video_file)
        
        # 2. Persist to PostgreSQL
        new_task = AITask(
            task_type="video_summary",
            payload=minio_payload, # Stores MinIO path info
            status="QUEUED",
            user_id="admin"
        )
        db.add(new_task)
        db.commit()
        db.refresh(new_task)

        # 3. Push to Redis queue
        redis_client.xadd(
            "stream:video_processing",
            {"task_id": str(new_task.id)}
        )

        return {
            "task_id": new_task.id,
            "status": "QUEUED",
            "storage": "minio",
            "object_key": minio_payload["video_key"]
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Upload task failed: {str(e)}")