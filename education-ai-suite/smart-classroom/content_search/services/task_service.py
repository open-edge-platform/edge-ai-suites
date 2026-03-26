# services/task_service.py

import traceback
import asyncio
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks
from database import SessionLocal
from crud.task_crud import task_crud
from schemas.task import TaskStatus
from services.search_service import search_service 
from core.models import AITask

class TaskService:
    @staticmethod
    async def handle_file_upload(
        db: Session, 
        minio_payload: dict, 
        background_tasks: BackgroundTasks,
        should_ingest: bool = False  # <--- 用这个开关来区分接口意图
    ):
        try:
            # 1. 统一创建任务记录
            task = task_crud.create_task(
                db, 
                task_type="file_search", 
                payload=minio_payload, 
                status=TaskStatus.PROCESSING
            )
            
            # 2. 如果需要 Ingest，就挂载后台任务；如果不需要，任务直接完成
            if should_ingest:
                background_tasks.add_task(TaskService.execute_worker_logic, str(task.id))
            else:
                # 纯上传接口，直接标记完成
                task.status = "COMPLETED"
                task.result = {"message": "Upload only, no ingest requested"}
                db.commit()

            return {"task_id": str(task.id), "status": task.status}
        except Exception as e:
            traceback.print_exc()
            raise e

    @staticmethod
    def execute_worker_logic(task_id: str):
        """这就是你之前 Worker 里的核心 AI 逻辑"""
        print(f"🚀 [BACKGROUND] Starting AI Ingest for Task {task_id}", flush=True)
        
        with SessionLocal() as db:
            task = db.query(AITask).filter(AITask.id == task_id).first()
            if not task: return

            try:
                # 获取文件 Key 并调用 AI 服务
                file_key = task.payload.get('file_key') or task.payload.get('video_key')
                
                # 模拟你之前的 Worker 逻辑
                ai_result = asyncio.run(search_service.trigger_ingest(file_key))
                
                task.status = "COMPLETED"
                task.result = ai_result
                db.commit()
                print(f"✅ Task {task_id} ingest completed", flush=True)

            except Exception as e:
                task.status = "FAILED"
                task.result = {"error": str(e)}
                db.commit()
                print(f"❌ Task {task_id} failed: {e}", flush=True)

task_service = TaskService()