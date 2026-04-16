#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import urllib.parse
import mimetypes
import json
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, BackgroundTasks, Form, Request
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import text
import re
from utils.database import get_db
from utils.task_service import task_service
from utils.storage_service import storage_service
from utils.asset_service import asset_service
from utils.search_service import search_service
from utils.core_responses import resp_200, fail_task_not_found, fail_process_failed, fail_processing
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
        return resp_200(code=40000, message="file_key is required")

    bucket_name = payload.get("bucket_name", "content-search")

    meta = payload.get("meta", {})
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except:
            meta = {"raw_info": meta}

    storage_payload = {
        "file_key": file_key,
        "bucket_name": bucket_name,
        "meta": meta,
        "vs_options": {
            "prompt": payload.get("prompt"),
            "chunk_duration_s": payload.get("chunk_duration")
        }
    }

    result = await task_service.handle_file_ingest(db, storage_payload, background_tasks)

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
async def download_file(request: Request, file_key: str, inline: bool = False):
    """
    Download or preview a file with HTTP Range support for video streaming
    e.g:
      - GET /download?file_key=runs/run_xxx/raw/video/default/test.mp4  (download)
      - GET /download?file_key=runs/run_xxx/raw/video/default/test.mp4&inline=true  (preview with range support)
    """
    filename = file_key.split('/')[-1]
    content_type, _ = mimetypes.guess_type(filename)
    if not content_type:
        content_type = "application/octet-stream"

    encoded_filename = urllib.parse.quote(filename)
    disposition_type = "inline" if inline else "attachment"

    # Get file size
    try:
        file_size = storage_service.get_file_size(file_key)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"File not found: {str(e)}")

    # Parse Range header
    range_header = request.headers.get("range")

    if range_header:
        # Parse range like "bytes=0-1023" or "bytes=1024-"
        range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if not range_match:
            raise HTTPException(status_code=416, detail="Invalid range")

        start = int(range_match.group(1))
        end = int(range_match.group(2)) if range_match.group(2) else file_size - 1

        # Validate range
        if start >= file_size or end >= file_size or start > end:
            raise HTTPException(status_code=416, detail="Range not satisfiable")

        content_length = end - start + 1

        # Read the range from file
        file_stream = await storage_service.get_file_stream(file_key)
        file_stream.seek(start)

        def iter_range():
            remaining = content_length
            chunk_size = 8192
            try:
                while remaining > 0:
                    chunk = file_stream.read(min(chunk_size, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
            finally:
                file_stream.close()

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Disposition": f"{disposition_type}; filename=\"{encoded_filename}\"; filename*=UTF-8''{encoded_filename}",
            "Access-Control-Expose-Headers": "Content-Disposition, Content-Range, Accept-Ranges"
        }

        return StreamingResponse(
            iter_range(),
            status_code=206,
            media_type=content_type,
            headers=headers
        )
    else:
        # No range requested, return full file
        file_stream = await storage_service.get_file_stream(file_key)

        headers = {
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Content-Disposition": f"{disposition_type}; filename=\"{encoded_filename}\"; filename*=UTF-8''{encoded_filename}",
            "Access-Control-Expose-Headers": "Content-Disposition, Accept-Ranges"
        }

        return StreamingResponse(
            file_stream,
            media_type=content_type,
            headers=headers
        )

@router.delete("/cleanup-task/{task_id}")
async def delete_specific_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    task_sql = text("SELECT id, payload FROM edu_ai_tasks WHERE id = :tid")
    task_row = db.execute(task_sql, {"tid": task_id}).fetchone()
    if not task_row:
        return resp_200(**fail_task_not_found())
    record = dict(task_row._mapping)
    current_status = record.get("status")
    if current_status == "processing":
        return resp_200(**fail_processing())
    try:
        raw_payload = record.get('payload')
        payload = json.loads(raw_payload) if isinstance(raw_payload, str) else (raw_payload or {})
    except Exception:
        payload = {}

    f_path = payload.get("file_key")
    f_bucket = payload.get("bucket") or payload.get("bucket_name")
    f_hash = payload.get("file_hash")

    try:
        if storage_service.file_exists(f_path):
            storage_service.delete_file(f_path)

        if await search_service.check_file_exists(f_path, bucket_name=f_bucket):
            await search_service.delete_file_index(f_path, bucket_name=f_bucket)

        if f_hash:
            db.execute(text("DELETE FROM file_assets WHERE file_hash = :h"), {"h": f_hash.strip()})

        db.execute(text("DELETE FROM edu_ai_tasks WHERE id = :tid"), {"tid": task_id.strip()})
        db.commit()

        return resp_200(
            message="Cleanup completed",
            data={
                "task_id": task_id,
                "status": "COMPLETED"
            }
        )

    except Exception as e:
        db.rollback()
        return resp_200(**fail_process_failed(str(e)))
