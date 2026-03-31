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
import urllib.parse
import mimetypes
import json
from utils.core_responses import resp_200

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

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
    text: str
    bucket_name: Optional[str] = None
    file_path: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
@router.post("/ingest-text")
async def ingest_raw_text(
    request: IngestTextRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    payload = request.model_dump() 

    if "tags" not in payload["meta"] or payload["meta"]["tags"] is None:
        payload["meta"]["tags"] = ["default"]

    result = await task_service.handle_text_ingest(
        db,
        payload,
        background_tasks
    )

    return resp_200(
        data={
            "task_id": str(result["task_id"]),
            "status": result["status"]
        },
        message="Text ingestion started"
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
    minio_payload = await storage_service.upload_and_prepare_payload(file)
    
    if meta:
        try:
            minio_payload["meta"] = json.loads(meta)
        except:
            minio_payload["meta"] = {"raw_info": meta}
    else:
        minio_payload["meta"] = {}

    minio_payload["vs_options"] = {
        "prompt": prompt,
        "chunk_duration_s": chunk_duration
    }

    result = await task_service.handle_file_upload(
        db, 
        minio_payload, 
        background_tasks, 
        should_ingest=True
    )

    return resp_200(
        data={
            "task_id": str(result["task_id"]),
            "status": result["status"],
            "file_key": minio_payload["file_key"]
        },
        message="Upload and Ingest started"
    )

# @router.post("/search")
# async def file_search(payload: dict):
#     query = payload.get("query")
#     limit = payload.get("max_num_results", 3)
#     if not query:
#         raise HTTPException(status_code=400, detail="Query cannot be empty")

#     search_data = await search_service.semantic_search(query, limit)
#     return resp_200(data=search_data, message="Resource found")

@router.post("/search")
async def file_search(payload: dict):
    query = payload.get("query")
    image_base64 = payload.get("image_base64")
    filters = payload.get("filter")
    limit = payload.get("max_num_results", 10)

    if not query and not image_base64:
        raise HTTPException(status_code=400, detail="Either 'query' or 'image_base64' must be provided")

    if query and image_base64:
        raise HTTPException(status_code=400, detail="Provide only one of 'query' or 'image_base64'")

    search_payload = {
        "max_num_results": limit
    }

    if query:
        search_payload["query"] = query
    else:
        search_payload["image_base64"] = image_base64

    if filters:
        search_payload["filter"] = filters

    search_data = await search_service.semantic_search(search_payload)

    return resp_200(data=search_data, message="Search completed")

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
