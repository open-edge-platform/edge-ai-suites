from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from database import get_db
from crud.task_crud import task_crud
from uuid import UUID
from core.models import AITask
from core.responses import resp_200

router = APIRouter()
@router.get("/list")
def list_tasks(
    status: Optional[str] = Query(None, description="Filter by status: QUEUED, PROCESSING, COMPLETED, FAILED"),
    limit: int = Query(100, ge=1, le=1000, description="Max number of tasks to return. Default is 100, max 1000"),
    db: Session = Depends(get_db)
):
    query = db.query(AITask)
    if status:
        query = query.filter(AITask.status == status.upper())
    tasks = query.order_by(AITask.created_at.desc()).limit(limit).all()
    return resp_200(data=tasks, message="Success")

@router.get("/query/{task_id}")
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
