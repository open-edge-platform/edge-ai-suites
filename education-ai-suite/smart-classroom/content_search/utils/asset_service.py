#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import hashlib
import json
from sqlalchemy.orm import Session
from fastapi import UploadFile, BackgroundTasks

from utils.core_models import FileAsset
from utils.storage_service import storage_service
from utils.task_service import task_service

class AssetService:
    @staticmethod
    def parse_meta(meta_str: str) -> dict:
        if not meta_str:
            return {}
        try:
            return json.loads(meta_str)
        except (json.JSONDecodeError, TypeError):
            return {"info": meta_str}

    @staticmethod
    async def _get_file_hash_and_asset(db: Session, file: UploadFile):
        content = await file.read()
        file_hash = hashlib.sha256(content).hexdigest()
        await file.seek(0)

        existing_asset = db.query(FileAsset).filter(FileAsset.file_hash == file_hash).first()
        return file_hash, existing_asset

    @staticmethod
    def _handle_deduplication_policy(existing_asset: FileAsset, file_hash: str):
        return {
            "is_biz_error": True,
            "code": 40901,
            "message": "Upload failed: File already exists.",
            "data": {
                "file_hash": file_hash,
                "file_name": existing_asset.file_name,
                "created_at": str(existing_asset.created_at)
            }
        }

    @staticmethod
    async def _prepare_and_upload_asset(db: Session, file: UploadFile, **kwargs) -> dict:
        file_hash, existing_asset = await AssetService._get_file_hash_and_asset(db, file)

        if existing_asset:
            print(f"[ASSET] File existed! filename: {file.filename}, Hash: {file_hash}")
            return AssetService._handle_deduplication_policy(existing_asset, file_hash)

        print(f"[ASSET] New upload: {file.filename}", flush=True)
        payload = await storage_service.upload_and_prepare_payload(file)
        payload.update({
            "is_biz_error": False,
            "file_hash": file_hash,
            "file_name": file.filename,
            "content_type": file.content_type,
            "size_bytes": file.size,
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