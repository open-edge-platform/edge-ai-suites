#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import traceback
import asyncio
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks
from utils.database import SessionLocal
from utils.crud_task import task_crud
from utils.schemas_task import TaskStatus
from utils.search_service import search_service 
from utils.storage_service import storage_service 
from utils.video_service import video_service 
from utils.core_models import FileAsset, AITask

class TaskService:
    @staticmethod
    async def handle_file_upload(
        db: Session, 
        minio_payload: dict, 
        background_tasks: BackgroundTasks,
        should_ingest: bool = False
    ):
        try:
            file_hash = minio_payload.get("file_hash")
            existing_asset = db.query(FileAsset).filter(FileAsset.file_hash == file_hash).first()
            if not existing_asset:
                new_asset = FileAsset(
                    file_hash=file_hash,
                    file_name=minio_payload.get("file_name", "unknown"),
                    file_path=minio_payload.get("file_key"),
                    bucket_name=minio_payload.get("bucket_name") or "content-search",
                    content_type=minio_payload.get("content_type"),
                    size_bytes=minio_payload.get("size_bytes", 0),
                    meta=minio_payload.get("meta", {})
                )
                db.add(new_asset)
                db.commit() 
                print(f"[ASSET] Successfully saved new asset: {file_hash}", flush=True)
            task = task_crud.create_task(
                db, 
                task_type="file_search", 
                payload=minio_payload, 
                status=TaskStatus.PROCESSING
            )

            if should_ingest:
                background_tasks.add_task(TaskService.execute_worker_logic, str(task.id))
            else:
                task.status = "COMPLETED"
                task.result = {
                    "message": "Upload successful",
                    "file_key": minio_payload.get("file_key"),
                    "bucket_name": minio_payload.get("bucket_name"),
                    "file_hash": minio_payload.get("file_hash")
                }
                db.commit()

            return {"task_id": str(task.id), "status": task.status}
        except Exception as e:
            db.rollback()
            traceback.print_exc()
            raise e

    @staticmethod
    async def handle_file_ingest(
        db: Session,
        payload: dict,
        background_tasks: BackgroundTasks
    ):
        try:
            task = task_crud.create_task(
                db, 
                task_type="file_ingest_only",
                payload=payload,
                status=TaskStatus.PROCESSING
            )

            background_tasks.add_task(TaskService.execute_worker_logic, str(task.id))

            return {"task_id": str(task.id), "status": task.status}

        except Exception as e:
            traceback.print_exc()
            raise e

    @staticmethod
    async def handle_text_ingest(db: Session, request_data: dict, background_tasks: BackgroundTasks):
        payload = request_data.copy()

        meta = payload.get("meta", {})
        if "tags" not in meta or not meta["tags"]:
            meta["tags"] = ["default"]
        payload["meta"] = meta

        task = task_crud.create_task(
            db, 
            task_type="text_ingest", 
            payload=payload, 
            status=TaskStatus.PROCESSING
        )

        background_tasks.add_task(TaskService.execute_worker_logic, str(task.id))

        return {"task_id": str(task.id), "status": task.status}

    @staticmethod
    async def handle_sync_search(db: Session, payload: dict):
        task = task_crud.create_task(
            db, 
            task_type="file_search", 
            payload=payload, 
            status=TaskStatus.PROCESSING
        )
        db.commit()

        try:
            search_data = await search_service.semantic_search(payload)
            task.status = TaskStatus.COMPLETED
            task.result = search_data
            db.commit()
            return {
                "task_id": str(task.id),
                "status": task.status,
                "results": search_data.get("results", [])
            }
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.result = {"error": str(e)}
            db.commit()
            return {"task_id": str(task.id), "status": task.status, "error": str(e)}

    @staticmethod
    def execute_worker_logic(task_id: str):
        print(f"[BACKGROUND] Starting Ingest for Task {task_id}", flush=True)
        with SessionLocal() as db:
            task = db.query(AITask).filter(AITask.id == task_id).first()
            if not task: return
            try:
                file_key = (task.payload.get('file_key') or 
                        task.payload.get('file_path') or 
                        task.payload.get('video_key') or "")
                bucket_name = task.payload.get('bucket_name')
                is_video = any(file_key.lower().endswith(ext) for ext in ['.mp4', '.avi', '.mov', '.mkv'])

                if task.task_type == "text_ingest":
                    text_content = task.payload.get("text")

                    if not text_content and file_key:
                        print(f"[WORKER] Fetching text from MinIO: {file_key}", flush=True)
                        file_data = asyncio.run(storage_service.get_file_content(file_key, bucket_name))
                        text_content = file_data.decode("utf-8")

                    ai_result = asyncio.run(search_service.ingest_text(
                        text=text_content,
                        file_path=file_key,
                        bucket_name=bucket_name,
                        meta=task.payload.get("meta")
                    ))

                else:
                    ai_result = asyncio.run(search_service.trigger_ingest(
                        file_path=file_key, 
                        bucket_name=bucket_name
                    ))

                if is_video and ai_result and "error" not in ai_result:
                    try:
                        payload = task.payload if task.payload else {}
                        raw_meta = payload.get("meta", {})
                        if isinstance(raw_meta, str):
                            try:
                                import json
                                raw_meta = json.loads(raw_meta)
                            except:
                                raw_meta = {}

                        user_tags = raw_meta.get("tags", [])
                        if not user_tags:
                            user_tags = ["default_video"]

                        vs_options = payload.get("vs_options", {})
                        custom_prompt = vs_options.get("prompt")
                        chunk_duration = vs_options.get("chunk_duration_s")

                        print(f"[VIDEO] Triggering summarization for {file_key}...", flush=True)
                        print(f"[VIDEO] Final tags: {user_tags}, Prompt: {custom_prompt}", flush=True)

                        summary_res = asyncio.run(video_service.trigger_summarization(
                            file_key=file_key,
                            bucket_name=bucket_name,
                            tags=user_tags,
                            prompt=custom_prompt,
                            chunk_duration=chunk_duration
                        ))

                        ai_result["video_summary"] = summary_res

                    except Exception as ve:
                        import traceback
                        print(f"[WARN] Video summarization failed: {ve}", flush=True)
                        traceback.print_exc()
                        ai_result["video_summary_error"] = str(ve)

                if ai_result and "error" not in ai_result:
                    task.status = TaskStatus.COMPLETED
                    task.result = ai_result
                    print(f"[OK] Task {task_id} completed", flush=True)
                else:
                    task.status = TaskStatus.FAILED
                    task.result = ai_result or {"error": "Unknown error from search service"}
                    print(f"[FAILED] Task {task_id} failed: {task.result}", flush=True)

                db.commit()

            except Exception as e:
                task.status = "FAILED"
                task.result = {"error": str(e)}
                db.commit()
                print(f"[FAILED] Task {task_id} failed: {e}", flush=True)

task_service = TaskService()
