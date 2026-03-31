#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import hashlib
import json
import traceback
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
    async def process_upload_and_ingest(
        db: Session, 
        file: UploadFile, 
        background_tasks: BackgroundTasks,
        **kwargs
    ):
        try:
            file_hash, existing_asset = await AssetService._get_file_hash_and_asset(db, file)

            if existing_asset:
                print(f"[ASSET] Ingest hit deduplication: {file_hash}", flush=True)
                return await task_service.handle_existing_asset_task(db, existing_asset, file_hash)

            minio_payload = await storage_service.upload_and_prepare_payload(file)
            minio_payload.update({
                "file_hash": file_hash,
                "is_deduplicated": False,
                **kwargs
            })

            return await task_service.handle_file_upload(
                db, minio_payload, background_tasks, should_ingest=True
            )
        except Exception as e:
            traceback.print_exc()
            raise e

    @staticmethod
    async def process_simple_upload(
        db: Session,
        file: UploadFile,
        background_tasks: BackgroundTasks
    ):
        try:
            file_hash, existing_asset = await AssetService._get_file_hash_and_asset(db, file)

            if existing_asset:
                print(f"[ASSET] Simple upload hit: {file_hash}", flush=True)
                minio_payload = {
                    "file_key": existing_asset.file_path,
                    "bucket_name": existing_asset.bucket_name,
                    "file_hash": file_hash,
                    "is_deduplicated": True
                }
                return await task_service.handle_file_upload(
                    db, minio_payload, background_tasks, should_ingest=False
                )

            print(f"[ASSET] New simple upload: {file.filename}", flush=True)
            minio_payload = await storage_service.upload_and_prepare_payload(file)
            minio_payload.update({
                "file_hash": file_hash,
                "is_deduplicated": False
            })

            return await task_service.handle_file_upload(
                db, minio_payload, background_tasks, should_ingest=False
            )
        except Exception as e:
            traceback.print_exc()
            raise e

asset_service = AssetService()