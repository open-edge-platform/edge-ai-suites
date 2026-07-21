from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from api.schemas import (
    GradingTaskControlResponse,
    GradingTaskCreateRequest,
    GradingTaskCreateResponse,
    GradingTaskResultResponse,
    GradingTaskStatusResponse,
    HealthResponse,
    RubricUploadResponse,
)
from services.grading_service_impl import (
    create_task as create_task_dispatch,
    get_health,
    get_task_result as get_task_result_impl,
    get_task_status as get_task_status_impl,
    request_task_cancel as request_task_cancel_impl,
    request_task_pause as request_task_pause_impl,
    request_task_resume as request_task_resume_impl,
    save_uploaded_rubric,
)


def create_router(language: str) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["grading"])

    @router.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(**get_health(language))

    @router.post("/rubrics/upload", response_model=RubricUploadResponse)
    async def upload_rubric(file: UploadFile = File(...)) -> RubricUploadResponse:
        try:
            content = await file.read()
            return RubricUploadResponse(**save_uploaded_rubric(filename=file.filename, content=content))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"unexpected error: {exc}") from exc

    @router.post("/grading/tasks", response_model=GradingTaskCreateResponse)
    async def create_task(req: GradingTaskCreateRequest) -> GradingTaskCreateResponse:
        try:
            payload = {
                "paper_path": req.paper_path,
                "rubric_path": req.rubric_path,
                "exam_id": req.exam_id,
            }
            task = create_task_dispatch(task_type="grading.run", payload=payload)
            return GradingTaskCreateResponse(
                task_id=task["job_id"],
                task_type=task["task_type"],
                status=task["status"],
                current_step=task["current_step"],
                progress=task["progress"],
                created_at=task["created_at"],
                log_path=task.get("log_path"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"unexpected error: {exc}") from exc

    @router.get("/grading/tasks/{task_id}", response_model=GradingTaskStatusResponse)
    async def get_task_status(task_id: str) -> GradingTaskStatusResponse:
        try:
            task = get_task_status_impl(task_id)
            return GradingTaskStatusResponse(
                task_id=task["job_id"],
                task_type=task["task_type"],
                status=task["status"],
                current_step=task["current_step"],
                progress=task["progress"],
                error_message=task.get("error_message"),
                created_at=task["created_at"],
                updated_at=task["updated_at"],
                log_path=task.get("log_path"),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"task not found: {task_id}") from exc

    @router.get("/grading/tasks/{task_id}/result", response_model=GradingTaskResultResponse)
    async def get_task_result(task_id: str) -> GradingTaskResultResponse:
        try:
            result = get_task_result_impl(task_id)
            return GradingTaskResultResponse(
                task_id=result["task_id"],
                task_type=result["task_type"],
                status=result["status"],
                result=result["result"],
                log_path=result.get("result", {}).get("log_path"),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"task not found: {task_id}") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"unexpected error: {exc}") from exc

    def _control_response(task: dict) -> GradingTaskControlResponse:
        return GradingTaskControlResponse(
            task_id=task["job_id"],
            task_type=task["task_type"],
            status=task["status"],
            current_step=task["current_step"],
            progress=task["progress"],
            control_action=task.get("control_action"),
            updated_at=task["updated_at"],
            log_path=task.get("log_path"),
        )

    @router.post("/grading/tasks/{task_id}/pause", response_model=GradingTaskControlResponse)
    async def pause_task(task_id: str) -> GradingTaskControlResponse:
        try:
            return _control_response(request_task_pause_impl(task_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"task not found: {task_id}") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/grading/tasks/{task_id}/resume", response_model=GradingTaskControlResponse)
    async def resume_task(task_id: str) -> GradingTaskControlResponse:
        try:
            return _control_response(request_task_resume_impl(task_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"task not found: {task_id}") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/grading/tasks/{task_id}/cancel", response_model=GradingTaskControlResponse)
    async def cancel_task(task_id: str) -> GradingTaskControlResponse:
        try:
            return _control_response(request_task_cancel_impl(task_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"task not found: {task_id}") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return router
