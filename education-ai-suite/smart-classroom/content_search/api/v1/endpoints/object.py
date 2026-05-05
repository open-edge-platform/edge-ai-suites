#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import urllib.parse
import mimetypes
import json
import logging
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

logger = logging.getLogger(__name__)

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

@router.get("/tags")
def list_tags(db: Session = Depends(get_db)):
    """Return all unique tags from successfully stored file assets."""
    rows = db.execute(text("SELECT meta FROM file_assets WHERE meta IS NOT NULL")).fetchall()
    tag_set: set[str] = set()
    for row in rows:
        raw = row._mapping.get("meta")
        if not raw:
            continue
        meta = json.loads(raw) if isinstance(raw, str) else raw
        tags = meta.get("tags") if isinstance(meta, dict) else None
        if isinstance(tags, list):
            for t in tags:
                if isinstance(t, str) and t.strip():
                    tag_set.add(t.strip())
    return resp_200(data=sorted(tag_set), message="Tags retrieved")

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

@router.delete("/files/{file_hash}")
async def delete_file_by_hash(
    file_hash: str,
    force: bool = False,
    db: Session = Depends(get_db)
):
    if len(file_hash) != 64 or not all(c in '0123456789abcdef' for c in file_hash.lower()):
        raise HTTPException(
            status_code=400,
            detail="Invalid file_hash format. Expected 64-character hex string."
        )

    file_record = db.execute(
        text("SELECT file_hash, file_name, file_path, bucket_name FROM file_assets WHERE file_hash = :h"),
        {"h": file_hash}
    ).fetchone()

    if not file_record:
        raise HTTPException(
            status_code=404,
            detail=f"File with hash {file_hash} not found in database"
        )

    f_hash, f_name, f_path, f_bucket = file_record

    deletion_results = {
        "file_hash": f_hash,
        "file_name": f_name,
        "file_path": f_path,
        "bucket_name": f_bucket,
        "storage_deleted": False,
        "index_deleted": False,
        "metadata_deleted": False,
        "tasks_deleted": 0,
        "errors": []
    }

    logger.info(f"Deleting file from LocalStorage: {f_path}")
    try:
        if storage_service.file_exists(f_path):
            storage_service.delete_file(f_path)
            deletion_results["storage_deleted"] = True
            logger.info(f"Deleted file from storage: {f_path}")
        else:
            logger.warning(f"File not found in storage: {f_path}")
            deletion_results["storage_deleted"] = True
    except Exception as e:
        error_msg = f"Failed to delete from storage: {str(e)}"
        deletion_results["errors"].append(error_msg)
        logger.error(error_msg)
        if not force:
            raise HTTPException(status_code=500, detail=error_msg)

    logger.info(f"Deleting indices from ChromaDB: {f_path}")
    try:
        chroma_exists = await search_service.check_file_exists(f_path, bucket_name=f_bucket)
        if chroma_exists:
            await search_service.delete_file_index(f_path, bucket_name=f_bucket)
            deletion_results["index_deleted"] = True
            logger.info(f"Deleted index from ChromaDB: {f_path}")
        else:
            logger.warning(f"Index not found in ChromaDB: {f_path}")
            deletion_results["index_deleted"] = True
    except Exception as e:
        error_msg = f"Failed to delete from ChromaDB: {str(e)}"
        deletion_results["errors"].append(error_msg)
        logger.error(error_msg)
        if not force:
            db.rollback()
            raise HTTPException(status_code=500, detail=error_msg)

    logger.info(f"Deleting metadata from file_assets: {f_hash}")
    try:
        result = db.execute(text("DELETE FROM file_assets WHERE file_hash = :h"), {"h": f_hash})
        if result.rowcount > 0:
            deletion_results["metadata_deleted"] = True
            logger.info(f"Deleted metadata from file_assets: {f_hash}")
        else:
            logger.warning(f"No metadata found to delete for hash: {f_hash}")
    except Exception as e:
        error_msg = f"Failed to delete metadata: {str(e)}"
        deletion_results["errors"].append(error_msg)
        logger.error(error_msg)
        db.rollback()
        if not force:
            raise HTTPException(status_code=500, detail=error_msg)

    logger.info(f"Deleting associated tasks for file_hash: {f_hash}")
    try:
        result = db.execute(
            text("DELETE FROM edu_ai_tasks WHERE payload LIKE :pattern"),
            {"pattern": f"%{f_hash}%"}
        )
        deletion_results["tasks_deleted"] = result.rowcount
        if result.rowcount > 0:
            logger.info(f"Deleted {result.rowcount} associated tasks")
        else:
            logger.info("No associated tasks found for this file")
    except Exception as e:
        error_msg = f"Failed to delete tasks: {str(e)}"
        deletion_results["errors"].append(error_msg)
        logger.error(error_msg)

    try:
        db.commit()
        logger.info("All database changes committed successfully")
    except Exception as e:
        db.rollback()
        error_msg = f"Failed to commit changes: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

    all_deleted = (
        deletion_results["storage_deleted"] and
        deletion_results["index_deleted"] and
        deletion_results["metadata_deleted"]
    )

    if all_deleted and not deletion_results["errors"]:
        message = "File and all associated data deleted successfully"
        code = 20000
    elif all_deleted and deletion_results["errors"]:
        message = "File deleted with some warnings"
        code = 20000
    else:
        message = "File partially deleted"
        code = 20000

    logger.info(f"Deletion complete for {f_hash}: storage={deletion_results['storage_deleted']}, "
                f"index={deletion_results['index_deleted']}, metadata={deletion_results['metadata_deleted']}, "
                f"tasks={deletion_results['tasks_deleted']}")

    return resp_200(
        code=code,
        data=deletion_results,
        message=message
    )

@router.get("/files/list")
async def list_all_files(
    page: int = 1,
    page_size: int = 50,
    file_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    try:
        page_size = min(max(1, page_size), 200)
        skip = (page - 1) * page_size

        from utils.core_models import FileAsset
        query = db.query(FileAsset)

        if file_type:
            query = query.filter(FileAsset.meta.contains(f'"type": "{file_type.lower()}"'))

        total = query.count()

        file_assets = query.order_by(FileAsset.created_at.desc()).offset(skip).limit(page_size).all()

        id_maps = await search_service.get_id_maps()
        visual_map = id_maps.get("visual", {})
        document_map = id_maps.get("document", {})
        video_summary_map = id_maps.get("video_summary", {})

        files_info = []
        for file_asset in file_assets:
            file_path = file_asset.file_path

            storage_exists = storage_service.file_exists(file_asset.file_path)

            collections_info = []
            total_vectors = 0
            indexed = False

            if file_path in visual_map:
                vector_ids = visual_map[file_path]
                collections_info.append({
                    "name": "visual",
                    "vector_count": len(vector_ids)
                })
                total_vectors += len(vector_ids)
                indexed = True

            if file_path in document_map:
                vector_ids = document_map[file_path]
                collections_info.append({
                    "name": "documents",
                    "vector_count": len(vector_ids)
                })
                total_vectors += len(vector_ids)
                indexed = True

            has_summary = file_path in video_summary_map
            if has_summary:
                summary_ids = video_summary_map[file_path]
                collections_info.append({
                    "name": "documents",
                    "type": "summary",
                    "vector_count": len(summary_ids)
                })
                total_vectors += len(summary_ids)

            if storage_exists and indexed:
                status = "synced"
            elif storage_exists and not indexed:
                status = "not_indexed"
            elif not storage_exists and indexed:
                status = "missing_file"
            else:
                status = "inconsistent"

            meta = file_asset.meta
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except:
                    meta = {}

            file_info = {
                "file_hash": file_asset.file_hash,
                "file_name": file_asset.file_name,
                "file_path": file_asset.file_path,
                "bucket_name": file_asset.bucket_name,
                "content_type": file_asset.content_type,
                "size_bytes": file_asset.size_bytes,
                "meta": meta,
                "created_at": file_asset.created_at.isoformat() if file_asset.created_at else None,
                "storage": {
                    "exists": storage_exists
                },
                "index": {
                    "indexed": indexed,
                    "vector_count": total_vectors,
                    "collections": collections_info,
                    "has_summary": has_summary
                },
                "status": status
            }

            files_info.append(file_info)

        stats = {
            "by_status": {},
            "by_type": {}
        }

        for file_info in files_info:
            status = file_info["status"]
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

            file_type_from_meta = file_info.get("meta", {}).get("type", "unknown")
            stats["by_type"][file_type_from_meta] = stats["by_type"].get(file_type_from_meta, 0) + 1

        return resp_200(
            data={
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size,
                "files": files_info,
                "statistics": stats
            },
            message="Files retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing files: {str(e)}")
