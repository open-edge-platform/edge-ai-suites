#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, BackgroundTasks, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from utils.database import get_db
from utils.task_service import task_service
from utils.storage_service import storage_service
from utils.search_service import search_service
from utils.asset_service import asset_service
import urllib.parse
import mimetypes
import json
from utils.core_responses import resp_200

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

router = APIRouter()

@router.post("/upload")
async def upload_video(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    result = await asset_service.process_simple_upload(
        db=db,
        file=file,
        background_tasks=background_tasks
    )
    return resp_200(data=result)

@router.post("/ingest")
async def ingest_existing_file(
    payload: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    file_key = payload.get("file_key")
    if not file_key:
        raise HTTPException(status_code=400, detail="file_key is required")

    bucket_name = payload.get("bucket_name", "content-search")

    meta = payload.get("meta", {})
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except:
            meta = {"raw_info": meta}

    minio_payload = {
        "file_key": file_key,
        "bucket_name": bucket_name,
        "meta": meta,
        "vs_options": {
            "prompt": payload.get("prompt"),
            "chunk_duration_s": payload.get("chunk_duration")
        }
    }

    result = await task_service.handle_file_ingest(db, minio_payload, background_tasks)

    return resp_200(
        data={
            "task_id": str(result["task_id"]),
            "status": result["status"],
            "file_key": file_key
        },
        message="Ingestion process started for existing file"
    )

class IngestTextRequest(BaseModel):
    text: Optional[str] = None
    bucket_name: Optional[str] = "content-search"
    file_key: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)

@router.post("/ingest-text")
async def ingest_raw_text(
    request: IngestTextRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):

    result = await task_service.handle_text_ingest(
        db,
        request.model_dump(), 
        background_tasks
    )

    return resp_200(
        data={
            "task_id": str(result["task_id"]),
            "status": result["status"]
        },
        message="Text ingestion task created successfully"
    )

@router.post("/upload-ingest")
async def upload_file_with_ingest(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    meta: str = Form(None),
    prompt: str = Form(None),
    chunk_duration: int = Form(None),
    db: Session = Depends(get_db)
):
    meta_data = asset_service.parse_meta(meta)

    result = await asset_service.process_upload_and_ingest(
        db, file, background_tasks,
        meta=meta_data,
        prompt=prompt,
        chunk_duration=chunk_duration
    )
    return resp_200(data=result)

@router.post("/search")
async def file_search(payload: dict, db: Session = Depends(get_db)):
    result = await task_service.handle_sync_search(db, payload)

    return resp_200(data=result, message="Search completed")

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
