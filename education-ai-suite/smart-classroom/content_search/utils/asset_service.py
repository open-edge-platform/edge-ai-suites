#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import json
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import UploadFile, BackgroundTasks

from utils.core_models import FileAsset
from utils.storage_service import storage_service
from utils.task_service import task_service

# Per-file upload size limits. Documents are the default; videos get a
# larger cap because classroom recordings are routinely hundreds of MB.
DOCUMENT_MAX_BYTES = 100 * 1024 * 1024       # 100 MiB
VIDEO_MAX_BYTES = 1024 * 1024 * 1024          # 1 GiB
VIDEO_CONTENT_PREFIX = "video/"
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}


def _max_bytes_for(file: UploadFile) -> int:
    ctype = (file.content_type or "").lower()
    if ctype.startswith(VIDEO_CONTENT_PREFIX):
        return VIDEO_MAX_BYTES
    name = (file.filename or "").lower()
    if any(name.endswith(ext) for ext in VIDEO_EXTENSIONS):
        return VIDEO_MAX_BYTES
    return DOCUMENT_MAX_BYTES


class AssetService:
    @staticmethod
    def parse_meta(meta_str: str) -> dict:
        if not meta_str:
            return {}
        try:
            parsed = json.loads(meta_str)
            if isinstance(parsed, str):
                parsed = json.loads(parsed)
            return parsed
        except (json.JSONDecodeError, TypeError):
            return {"info": meta_str}

    @staticmethod
    def _find_existing_asset(db: Session, file_hash: str) -> Optional[FileAsset]:
        return db.query(FileAsset).filter(FileAsset.file_hash == file_hash).first()

    @staticmethod
    def _handle_deduplication_policy(db: Session, existing_asset: FileAsset, file_hash: str):
        from utils.core_models import AITask

        all_tasks = db.query(AITask).order_by(AITask.created_at.desc()).all()

        related_task = None
        for task in all_tasks:
            payload = task.payload if isinstance(task.payload, dict) else {}
            if payload.get('file_hash') == file_hash:
                related_task = task
                break

        task_id = str(related_task.id) if related_task else None

        ocr_text_key = None
        if related_task and related_task.result:
            task_result = related_task.result if isinstance(related_task.result, dict) else {}
            ocr_text_key = task_result.get("ocr_text_key")

        data = {
            "file_hash": file_hash,
            "file_name": existing_asset.file_name,
            "created_at": str(existing_asset.created_at),
            "task_id": task_id
        }
        if ocr_text_key:
            data["ocr_text_key"] = ocr_text_key

        return {
            "is_biz_error": True,
            "code": 40901,
            "message": "Upload failed: File already exists.",
            "data": data
        }

    @staticmethod
    async def _prepare_and_upload_asset(db: Session, file: UploadFile, **kwargs) -> dict:
        max_bytes = _max_bytes_for(file)
        payload = await storage_service.upload_and_prepare_payload(
            file, max_size_bytes=max_bytes
        )
        file_hash = payload["file_hash"]

        existing_asset = AssetService._find_existing_asset(db, file_hash)
        if existing_asset:
            print(f"[ASSET] File existed! filename: {file.filename}, Hash: {file_hash}")
            # The file we just wrote is a duplicate; drop it so we don't
            # accumulate orphaned copies in the object store.
            try:
                storage_service.delete_file(payload["file_key"], missing_ok=True)
            except Exception:
                pass
            return AssetService._handle_deduplication_policy(db, existing_asset, file_hash)

        print(f"[ASSET] New upload: {file.filename}", flush=True)
        payload.update({
            "is_biz_error": False,
            "file_name": file.filename,
            "content_type": file.content_type,
            "bucket_name": payload.get("bucket_name") or "content-search",
            **kwargs
        })
        return payload

    @staticmethod
    async def process_simple_upload(db: Session, file: UploadFile, background_tasks: BackgroundTasks):
        payload = await AssetService._prepare_and_upload_asset(db, file)

        if payload.get("is_biz_error"):
            return payload

        return await task_service.handle_file_upload(db, payload, background_tasks, should_ingest=False)

    @staticmethod
    async def process_upload_and_ingest(db: Session, file: UploadFile, background_tasks: BackgroundTasks, **kwargs):
        payload = await AssetService._prepare_and_upload_asset(db, file, **kwargs)

        if payload.get("is_biz_error"):
            return payload

        return await task_service.handle_file_upload(db, payload, background_tasks, should_ingest=True)

asset_service = AssetService()