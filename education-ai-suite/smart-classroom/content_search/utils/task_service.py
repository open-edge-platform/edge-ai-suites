#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import os
import uuid
import traceback
import asyncio
from pathlib import Path
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks
import httpx
from utils.database import SessionLocal
from utils.crud_task import task_crud
from utils.schemas_task import TaskStatus
from utils.search_service import search_service
from utils.storage_service import storage_service
from utils.video_service import video_service
from utils.core_models import FileAsset, AITask

OCR_BASE_URL = os.getenv("OCR_SERVICE_URL", "http://127.0.0.1:8000")
OCR_TIMEOUT = 120.0

VIDEO_SUMMARIZATION_ENABLED = os.getenv("VIDEO_SUMMARIZATION_ENABLED", "true").lower() in ("true", "1", "yes")

class TaskService:
    @staticmethod
    async def handle_file_upload(
        db: Session, 
        storage_payload: dict,
        background_tasks: BackgroundTasks,
        should_ingest: bool = False
    ):
        try:
            file_hash = storage_payload.get("file_hash")
            existing_asset = db.query(FileAsset).filter(FileAsset.file_hash == file_hash).first()
            if not existing_asset:
                new_asset = FileAsset(
                    file_hash=file_hash,
                    file_name=storage_payload.get("file_name", "unknown"),
                    file_path=storage_payload.get("file_key"),
                    bucket_name=storage_payload.get("bucket_name") or "content-search",
                    content_type=storage_payload.get("content_type"),
                    size_bytes=storage_payload.get("size_bytes", 0),
                    meta=storage_payload.get("meta", {})
                )
                db.add(new_asset)
                db.commit() 
                print(f"[ASSET] Successfully saved new asset: {file_hash}", flush=True)
            task = task_crud.create_task(
                db, 
                task_type="file_search", 
                payload=storage_payload,
                status=TaskStatus.PROCESSING
            )

            if should_ingest:
                background_tasks.add_task(TaskService.execute_worker_logic, str(task.id))
            else:
                task.status = "COMPLETED"
                task.result = {
                    "message": "Upload successful",
                    "file_key": storage_payload.get("file_key"),
                    "bucket_name": storage_payload.get("bucket_name"),
                    "file_hash": storage_payload.get("file_hash")
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
                        task.payload.get('file_path') or "")
                bucket_name = task.payload.get('bucket_name')
                is_video = any(file_key.lower().endswith(ext) for ext in ['.mp4', '.avi', '.mov', '.mkv'])

                ocr_file_key = None

                if task.task_type == "text_ingest":
                    text_content = task.payload.get("text")

                    if not text_content and file_key:
                        print(f"[WORKER] Fetching text from storage: {file_key}", flush=True)
                        file_data = asyncio.run(storage_service.get_file_content(file_key, bucket_name))
                        text_content = file_data.decode("utf-8")

                    ai_result = asyncio.run(search_service.ingest_text(
                        text=text_content,
                        file_path=file_key,
                        bucket_name=bucket_name,
                        meta=task.payload.get("meta")
                    ))

                else:
                    # OCR: detect handwritten PDF and extract text before ingestion
                    ocr_file_key = None
                    if file_key.lower().endswith('.pdf'):
                        ocr_file_key = TaskService._process_ocr(file_key)

                    # If OCR produced a .txt file, ingest that instead of the original PDF
                    ingest_key = ocr_file_key or file_key
                    ai_result = asyncio.run(search_service.trigger_ingest(
                        file_path=ingest_key,
                        bucket_name=bucket_name,
                        meta=task.payload.get("meta")
                    ))

                # Determine if video summarization should run for this task
                raw_meta = task.payload.get("meta", {})
                if isinstance(raw_meta, str):
                    try:
                        import json as _json
                        raw_meta = _json.loads(raw_meta)
                    except Exception:
                        raw_meta = {}
                user_vs_enabled = raw_meta.get("vs_enabled", False) if isinstance(raw_meta, dict) else False
                do_summarize = is_video and VIDEO_SUMMARIZATION_ENABLED and bool(user_vs_enabled)

                if ai_result and "error" not in ai_result:
                    task.status = TaskStatus.COMPLETED
                    if do_summarize:
                        ai_result["video_summary_status"] = "PROCESSING"
                    if ocr_file_key:
                        ai_result["ocr_text_key"] = ocr_file_key
                    task.result = ai_result
                    db.commit()
                    print(f"[OK] Task {task_id} ingest completed", flush=True)
                else:
                    task.status = TaskStatus.FAILED
                    task.result = ai_result or {"error": "Unknown error from search service"}
                    db.commit()
                    print(f"[FAILED] Task {task_id} failed: {task.result}", flush=True)

                # Video summarization runs after task is marked COMPLETED
                # so the file is already searchable during summarization
                if do_summarize and ai_result and "error" not in ai_result:
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

                        # Extract run_id from payload or file_key to ensure derived files use the same run_id
                        run_id = payload.get("run_id")
                        if not run_id and file_key.startswith("runs/"):
                            parts = file_key.split("/")
                            if len(parts) > 1:
                                run_id = parts[1]

                        print(f"[VIDEO] Triggering summarization for {file_key}...", flush=True)
                        print(f"[VIDEO] Using run_id: {run_id}, Final tags: {user_tags}, Prompt: {custom_prompt}", flush=True)

                        summary_res = asyncio.run(video_service.trigger_summarization(
                            file_key=file_key,
                            bucket_name=bucket_name,
                            tags=user_tags,
                            prompt=custom_prompt,
                            chunk_duration=chunk_duration,
                            run_id=run_id
                        ))

                        task.result = {**ai_result, "video_summary": summary_res, "video_summary_status": "COMPLETED"}
                        db.commit()
                        print(f"[OK] Task {task_id} video summarization completed", flush=True)

                    except Exception as ve:
                        import traceback
                        print(f"[WARN] Video summarization failed (task already COMPLETED): {ve}", flush=True)
                        traceback.print_exc()
                        task.result = {**ai_result, "video_summary_error": str(ve), "video_summary_status": "FAILED"}
                        db.commit()
                elif is_video and not do_summarize:
                    reason = "globally disabled" if not VIDEO_SUMMARIZATION_ENABLED else "disabled by user"
                    print(f"[VIDEO] Summarization {reason}, skipping for {file_key}", flush=True)

            except Exception as e:
                task.status = "FAILED"
                task.result = {"error": str(e)}
                db.commit()
                print(f"[FAILED] Task {task_id} failed: {e}", flush=True)

    @staticmethod
    def _process_ocr(file_key: str):
        """Detect if PDF is handwritten and extract text via OCR API. Returns .ocr.txt object key or None."""
        try:
            file_disk_path = str(storage_service.get_file_disk_path(file_key))
            session_id = str(uuid.uuid4())

            with httpx.Client(timeout=OCR_TIMEOUT) as client:
                # Step 1: detect if PDF is handwritten/scanned
                with open(file_disk_path, 'rb') as f:
                    detect_resp = client.post(
                        f"{OCR_BASE_URL}/ocr/detect-file",
                        files={'file': (Path(file_disk_path).name, f, 'application/pdf')}
                    )

                if detect_resp.status_code != 200:
                    return None

                is_digital = detect_resp.json().get("data", {}).get("is_digital", True)
                if is_digital:
                    return None

                # Step 2: extract text from handwritten PDF
                print(f"[OCR] Handwritten PDF detected, extracting text...", flush=True)
                with open(file_disk_path, 'rb') as f:
                    extract_resp = client.post(
                        f"{OCR_BASE_URL}/ocr/extract-text",
                        files={'file': (Path(file_disk_path).name, f, 'application/pdf')},
                        headers={'X-Session-ID': session_id}
                    )

                if extract_resp.status_code != 200:
                    print(f"[OCR] Text extraction failed: {extract_resp.status_code}", flush=True)
                    return None

                ocr_result_file = extract_resp.json().get("data", {}).get("result_file")
                if not ocr_result_file:
                    print(f"[OCR] No result_file in response", flush=True)
                    return None

                # OCR service returns path relative to smart-classroom/ (one level up)
                if not os.path.isabs(ocr_result_file) and not os.path.exists(ocr_result_file):
                    ocr_result_file = os.path.join("..", ocr_result_file)

                if not os.path.exists(ocr_result_file):
                    print(f"[OCR] Result file not found: {ocr_result_file}", flush=True)
                    return None

                # Step 3: read OCR text and save a copy to content_search local storage
                with open(ocr_result_file, 'r', encoding='utf-8') as tf:
                    ocr_text = tf.read()

                ocr_object_key = file_key.rsplit('.', 1)[0] + '.ocr.txt'
                storage_service._store.put_bytes(
                    ocr_object_key,
                    ocr_text.encode('utf-8'),
                    content_type="text/plain"
                )
                print(f"[OCR] Text saved to storage: {ocr_object_key}", flush=True)
                return ocr_object_key

        except Exception as e:
            print(f"[OCR] Processing skipped due to error: {e}", flush=True)
            return None


task_service = TaskService()
