from sqlalchemy.orm import Session
from typing import Optional, Any, Dict
from core.models import AITask
from schemas.task import TaskStatus

class TaskCRUD:
    @staticmethod
    def create_task(
        db: Session, 
        task_type: str, 
        payload: Dict[str, Any], 
        status: TaskStatus = TaskStatus.PENDING
    ) -> AITask:
        new_task = AITask(
            task_type=task_type, 
            payload=payload, 
            status=status.value if hasattr(status, 'value') else status, 
            user_id="admin"
        )
        db.add(new_task)
        db.commit()
        db.refresh(new_task)
        return new_task

    @staticmethod
    def update_task_status(
        db: Session, 
        task_id: int, 
        status: TaskStatus,
        result: Optional[Dict[str, Any]] = None
    ) -> Optional[AITask]:
        task = db.query(AITask).filter(AITask.id == task_id).first()
        if task:
            task.status = status.value if hasattr(status, 'value') else status
            if result:
                task.result = result
            db.commit()
            db.refresh(task)
        return task

    @staticmethod
    def get_task(db: Session, task_id: int) -> Optional[AITask]:
        return db.query(AITask).filter(AITask.id == task_id).first()

task_crud = TaskCRUD()