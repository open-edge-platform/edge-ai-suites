from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi import Query
from fastapi.responses import JSONResponse, Response

from api.schemas import (
    FsListResponse,
    GradingConfigResponse,
    GradingConfigUpdateRequest,
    GradingTaskControlResponse,
    RubricContentResponse,
    RubricUpdateRequest,
    RubricUpdateResponse,
    GradingTaskCreateRequest,
    GradingTaskCreateResponse,
    GradingTaskStatusResponse,
    TaskLogResponse,
    TaskSummaryJsonResponse,
    HealthResponse,
    RubricListResponse,
    RubricUploadResponse,
    TaskListResponse,
)
from services.grading_service_impl import (
    _dir_info as dir_info_impl,
    create_task as create_task_dispatch,
    delete_task as delete_task_impl,
    get_grading_config as get_grading_config_impl,
    update_grading_config as update_grading_config_impl,
    get_rubric_content as get_rubric_content_impl,
    update_rubric_content as update_rubric_content_impl,
    get_task_summary as get_task_summary_impl,
    get_student_result as get_student_result_impl,
    get_health,
    get_task_status as get_task_status_impl,
    list_directory as list_directory_impl,
    list_rubrics as list_rubrics_impl,
    list_tasks as list_tasks_impl,
    read_task_log as read_task_log_impl,
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

    @router.get("/rubrics", response_model=RubricListResponse)
    async def list_rubrics() -> RubricListResponse:
        return RubricListResponse(**list_rubrics_impl())

    @router.get("/fs/list", response_model=FsListResponse)
    async def list_fs(path: str | None = Query(default=None)) -> FsListResponse:
        try:
            return FsListResponse(**list_directory_impl(path))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"unexpected error: {exc}") from exc

    @router.get("/grading/config", response_model=GradingConfigResponse)
    async def get_config() -> GradingConfigResponse:
        return GradingConfigResponse(**get_grading_config_impl())

    @router.put("/grading/config", response_model=GradingConfigResponse)
    async def update_config(req: GradingConfigUpdateRequest) -> GradingConfigResponse:
        try:
            return GradingConfigResponse(**update_grading_config_impl(
                dpi=req.dpi,
                page_columns=req.page_columns,
                column_split_ratio=req.column_split_ratio,
                force_split=req.force_split,
                force_split_pairs=req.force_split_pairs,
                contrast_enhance=req.contrast_enhance,
                contrast_factor=req.contrast_factor,
                max_tokens=req.max_tokens,
                vlm_temperature=req.vlm_temperature,
                max_image_pixels=req.max_image_pixels,
                poll_interval=req.poll_interval,
                stable_checks=req.stable_checks,
                idle_timeout=req.idle_timeout,
                min_score=req.min_score,
                sort_boxes=req.sort_boxes,
                expand_margin=req.expand_margin,
                merge_overlapping=req.merge_overlapping,
                iou_threshold=req.iou_threshold,
            ))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"unexpected error: {exc}") from exc

    @router.post("/rubrics/upload", response_model=RubricUploadResponse)
    async def upload_rubric(file: UploadFile = File(...)) -> RubricUploadResponse:
        try:
            content = await file.read()
            return RubricUploadResponse(**save_uploaded_rubric(filename=file.filename, content=content))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"unexpected error: {exc}") from exc

    @router.get("/rubrics/{filename}/content", response_model=RubricContentResponse)
    async def get_rubric_content(filename: str) -> RubricContentResponse:
        try:
            return RubricContentResponse(**get_rubric_content_impl(filename))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"unexpected error: {exc}") from exc

    @router.put("/rubrics/{filename}/content", response_model=RubricUpdateResponse)
    async def update_rubric_content(filename: str, req: RubricUpdateRequest) -> RubricUpdateResponse:
        try:
            return RubricUpdateResponse(**update_rubric_content_impl(filename, req.content))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
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

    @router.get("/grading/tasks", response_model=TaskListResponse)
    async def list_tasks(status: str | None = None) -> TaskListResponse:
        return TaskListResponse(**list_tasks_impl(status=status))

    @router.get("/grading/tasks/{task_id}/summary", response_model=TaskSummaryJsonResponse)
    async def get_task_summary(task_id: str) -> TaskSummaryJsonResponse:
        try:
            return TaskSummaryJsonResponse(**get_task_summary_impl(task_id))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"unexpected error: {exc}") from exc

    @router.get("/grading/tasks/{task_id}/students/{slot}/result")
    async def get_student_result(task_id: str, slot: str) -> JSONResponse:
        try:
            return JSONResponse(content=get_student_result_impl(task_id, slot))
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
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
                dir_info=dir_info_impl(task),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"task not found: {task_id}") from exc

    @router.get("/grading/tasks/{task_id}/log", response_model=TaskLogResponse)
    async def get_task_log(task_id: str, tail: int = Query(default=50)) -> TaskLogResponse:
        try:
            return TaskLogResponse(**read_task_log_impl(task_id, tail=tail))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"task not found: {task_id}") from exc
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

    @router.delete("/grading/tasks/{task_id}", status_code=204, response_model=None, response_class=Response)
    async def delete_task(task_id: str) -> Response:
        try:
            delete_task_impl(task_id)
            return Response(status_code=204)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"task not found: {task_id}") from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"unexpected error: {exc}") from exc

    return router
