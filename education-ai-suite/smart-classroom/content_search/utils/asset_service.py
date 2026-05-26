#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import json
import os
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import UploadFile, BackgroundTasks

from utils.core_models import FileAsset
from utils.storage_service import storage_service
from utils.task_service import task_service

VIDEO_CONTENT_PREFIX = "video/"
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}


def _max_bytes_for(file: UploadFile) -> Optional[int]:
    document_max_mb = int(os.environ.get("DOCUMENT_MAX_MB", "100"))
    video_max_mb = int(os.environ.get("VIDEO_MAX_MB", "1024"))

    ctype = (file.content_type or "").lower()
    if ctype.startswith(VIDEO_CONTENT_PREFIX):
        return video_max_mb * 1024 * 1024
    name = (file.filename or "").lower()
    if any(name.endswith(ext) for ext in VIDEO_EXTENSIONS):
        return video_max_mb * 1024 * 1024
    return document_max_mb * 1024 * 1024


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
        from utils.core_models import AITask

        asset = db.query(FileAsset).filter(FileAsset.file_hash == file_hash).first()
        if not asset:
            return None

        # Allow re-upload if the associated task failed
        # Query all tasks and filter in Python to avoid SQLAlchemy JSON syntax issues
        all_tasks = db.query(AITask).order_by(AITask.created_at.desc()).all()

        related_task = None
        for task in all_tasks:
            payload = task.payload if isinstance(task.payload, dict) else {}
            if payload.get('file_hash') == file_hash:
                related_task = task
                break

        if related_task and related_task.status == "FAILED":
            print(f"[ASSET] Task {related_task.id} failed. Allowing re-upload for hash {file_hash}", flush=True)
            return None

        return asset

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
        max_size_bytes = _max_bytes_for(file)

        payload = await storage_service.upload_and_prepare_payload(
            file, max_size_bytes=max_size_bytes
        )

        if "validation_error" in payload:
            from utils.crud_task import task_crud
            from utils.schemas_task import TaskStatus

            error_code = 40002 if payload.get("error_type") == "invalid_file" else 41301

            failed_task = task_crud.create_task(
                db,
                task_type="file_search",
                payload={
                    "file_name": file.filename,
                    "content_type": file.content_type,
                    "validation_error": payload["validation_error"],
                    "error_type": payload["error_type"],
                    **kwargs
                },
                status=TaskStatus.FAILED
            )
            failed_task.result = {
                "error": payload["validation_error"],
                "error_type": payload["error_type"]
            }
            db.commit()

            return {
                "is_biz_error": True,
                "code": error_code,
                "message": f"Upload validation failed: {payload['validation_error']}",
                "data": {
                    "task_id": str(failed_task.id),
                    "file_name": file.filename,
                    "reason": payload["validation_error"]
                }
            }

        file_key = payload.get("file_key")
        file_name_lower = (file.filename or "").lower()

        if any(file_name_lower.endswith(ext) for ext in ['.pdf', '.mp4', '.avi', '.mov', '.mkv']):
            from utils.crud_task import task_crud
            from utils.schemas_task import TaskStatus
            from utils.file_validator import file_validator

            file_path = storage_service.get_file_disk_path(file_key)
            is_valid, error_msg = file_validator.validate_file_integrity(str(file_path))

            if not is_valid:
                print(f"[ASSET] File integrity check failed: {file.filename}, Error: {error_msg}", flush=True)

                try:
                    storage_service.delete_file(file_key, missing_ok=True)
                except Exception:
                    pass

                failed_task = task_crud.create_task(
                    db,
                    task_type="file_search",
                    payload={
                        "file_name": file.filename,
                        "content_type": file.content_type,
                        "file_key": file_key,
                        "validation_error": error_msg,
                        "error_type": "corrupted_file",
                        **kwargs
                    },
                    status=TaskStatus.FAILED
                )
                failed_task.result = {
                    "error": error_msg,
                    "error_type": "corrupted_file"
                }
                db.commit()

                return {
                    "is_biz_error": True,
                    "code": 40002,
                    "message": f"File integrity validation failed: {error_msg}",
                    "data": {
                        "task_id": str(failed_task.id),
                        "file_name": file.filename,
                        "reason": error_msg
                    }
                }

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