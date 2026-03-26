from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database import get_db
from services.task_service import task_service
from services.storage_service import storage_service
from services.search_service import search_service
import urllib.parse
import mimetypes
from core.responses import resp_200

router = APIRouter()

# @router.get("/files")

@router.post("/upload")
async def upload_video(background_tasks: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)):
    minio_payload = await storage_service.upload_and_prepare_payload(file)

    result = await task_service.handle_file_upload(db, minio_payload, background_tasks, should_ingest=False)
    return resp_200(
        data={
            "task_id": str(result["task_id"]),
            "status": result["status"]
        },
        message="File received, processing started."
    )

# @router.post("/ingest")

@router.post("/upload-ingest")
async def upload_file_with_ingest(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    minio_payload = await storage_service.upload_and_prepare_payload(file)
    result = await task_service.handle_file_upload(db, minio_payload, background_tasks, should_ingest=True)
    return resp_200(
        data={
            "task_id": str(result["task_id"]),
            "status": result["status"],
            "file_key": minio_payload["file_key"]
        },
        message="Upload and Ingest started"
    )

@router.post("/search")
async def file_search(payload: dict):
    query = payload.get("query")
    limit = payload.get("max_num_results", 3)
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    search_data = await search_service.semantic_search(query, limit)
    return resp_200(data=search_data, message="Resource found")

@router.get("/download")
async def download_file(file_key: str):
    """
    e.g: GET /download?file_key=runs/run_xxx/raw/video/default/test.mp4
    """
    file_stream = await storage_service.get_file_stream(file_key)

    filename = file_key.split('/')[-1]
    content_type, _ = mimetypes.guess_type(filename)
    if not content_type:
        content_type = "application/octet-stream"

    encoded_filename = urllib.parse.quote(filename)

    return StreamingResponse(
        file_stream,
        media_type=content_type,
        headers={
            "Content-Disposition": f"attachment; filename=\"{encoded_filename}\"; filename*=UTF-8''{encoded_filename}",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )
