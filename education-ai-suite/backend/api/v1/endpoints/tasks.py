from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session
from database import get_db
from services.task_service import task_service
from services.storage_service import storage_service
from crud.task_crud import task_crud
from uuid import UUID

router = APIRouter()

@router.post("/video-summary")
async def submit_summary(payload: dict, db: Session = Depends(get_db)):
    return await task_service.create_summary_task(db, payload)

@router.post("/video-upload")
async def upload_video(video_file: UploadFile = File(...), db: Session = Depends(get_db)):
    minio_payload = await storage_service.upload_and_prepare_payload(video_file)
    result = await task_service.handle_video_upload(db, minio_payload)
    return {
        "task_id": result["task_id"], 
        "status": result["status"], 
        "object_key": minio_payload["video_key"]
    }


@router.get("/task/{task_id}")
async def get_task(task_id: UUID, db: Session = Depends(get_db)):
    task = task_crud.get_task(db, str(task_id))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task