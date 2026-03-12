from sqlalchemy.orm import Session
from crud.task_crud import task_crud
from processor import run_dummy_ai_logic
from core.redis_client import redis_client

from schemas.task import TaskCreateRequest, TaskResponse, TaskStatus, RedisTaskMessage

class TaskService:
    @staticmethod
    async def create_summary_task(db: Session, raw_payload: dict):
        req = TaskCreateRequest(**raw_payload)

        task = task_crud.create_task(db, "video_summary", req.dict())

        if req.sync:
            task_crud.update_task_status(db, task.id, TaskStatus.PROCESSING)
            video_path = str(req.video_url)
            if not video_path.startswith('http'):
                print(f"Processing local file: {video_path}")
                
            result = await run_dummy_ai_logic(video_path)
            task = task_crud.update_task_status(db, task.id, TaskStatus.COMPLETED, result)

            return TaskResponse(
                task_id=task.id, 
                status=TaskStatus.COMPLETED, 
                result=result, 
                mode="synchronous"
            ).dict()
        else:
            task_crud.update_task_status(db, task.id, TaskStatus.QUEUED)

            msg = RedisTaskMessage(task_id=str(task.id))
            redis_client.xadd("stream:video_processing", msg.dict())
            
            return TaskResponse(
                task_id=task.id, 
                status=TaskStatus.QUEUED, 
                mode="asynchronous"
            ).dict()

    @staticmethod
    async def handle_video_upload(db: Session, minio_payload: dict):
        import traceback
        try:
            task = task_crud.create_task(db, "video_summary", minio_payload, status=TaskStatus.QUEUED)
            t_id = str(task.id)
            msg = RedisTaskMessage(task_id=t_id)

            redis_client.xadd("stream:video_processing", {"task_id": t_id})
            return TaskResponse(
                task_id=str(t_id),
                status=TaskStatus.QUEUED,
                mode="upload_async",
                result=None
            ).dict()

        except Exception as e:
            print("\n" + "="*50)
            print("❌ DETECTED ERROR IN handle_video_upload:")
            traceback.print_exc()
            print("="*50 + "\n")
            raise e

task_service = TaskService()