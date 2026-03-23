from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from crud.task_crud import task_crud
from uuid import UUID
from core.responses import resp_200

router = APIRouter()

@router.get("/{task_id}")
def get_task(task_id: UUID, db: Session = Depends(get_db)):
    task = task_crud.get_task(db, str(task_id))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return resp_200(
        data={
            "task_id": str(task.id),
            "status": task.status,
            # "progress": getattr(task, "progress", 0),
            "progress": 100,
            "result": task.result if task.status == "COMPLETED" else None
        },
        message="Query successful"
    )

# @router.get("/tasks")

# @router.post("/cancel/{task_id}")

# @router.post("/pause/{task_id}")

# @router.post("/resume/{task_id}")
