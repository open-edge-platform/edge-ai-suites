from sqlalchemy.orm import Session
from typing import Optional, Any, Dict
from core.models import AITask
from schemas.task import TaskStatus
from uuid import UUID

class TaskCRUD:
    @staticmethod
    def create_task(
        db: Session, 
        task_type: str, 
        payload: Dict[str, Any], 
        status: TaskStatus = TaskStatus.PENDING,
        progress: int = 0
    ) -> AITask:
        new_task = AITask(
            task_type=task_type, 
            payload=payload, 
            status=status.value if hasattr(status, 'value') else status, 
            progress=progress,
            user_id="admin"
        )
        db.add(new_task)
        db.commit()
        db.refresh(new_task)
        return new_task

    @staticmethod
    def update_task_status(
        db: Session, 
        task_id: UUID, 
        status: TaskStatus,
        progress: int = 0,
        result: Optional[Dict[str, Any]] = None
    ) -> Optional[AITask]:
        task = db.query(AITask).filter(AITask.id == task_id).first()
        if task:
            task.status = status.value if hasattr(status, 'value') else status
            task.progress = progress
            if result:
                task.result = result
            db.commit()
            db.refresh(task)
        return task

    @staticmethod
    def get_task(db: Session, task_id: int) -> Optional[AITask]:
        return db.query(AITask).filter(AITask.id == task_id).first()

task_crud = TaskCRUD()