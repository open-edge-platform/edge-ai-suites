from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    language: str
    dependencies: dict | None = None


class RubricGenerateRequest(BaseModel):
    input_path: str
    output_path: str
    question_key: str = "rubric"
    subjective_template_path: str | None = None


class RubricGenerateResponse(BaseModel):
    status: str
    output_path: str
    total_questions: int
    metadata_included: bool
    template_applied: bool


class RubricUploadResponse(BaseModel):
    status: str
    filename: str
    rubric_path: str
    size_bytes: int


class GradingJobCreateRequest(BaseModel):
    input_path: str
    output_path: str
    question_key: str = "rubric"
    subjective_template_path: str | None = None


class GradingJobCreateResponse(BaseModel):
    job_id: str
    status: str
    current_step: str
    progress: int
    created_at: str


class GradingJobStatusResponse(BaseModel):
    job_id: str
    task_type: str
    status: str
    current_step: str
    progress: int
    error_message: str | None = None
    created_at: str
    updated_at: str


class GradingJobResultResponse(BaseModel):
    job_id: str
    status: str
    result: dict


class GradingTaskCreateRequest(BaseModel):
    # Minimal grading request. dpi / answer_key / force_regrade all come from
    # the component config.yaml. student_id is derived from paper_path. Outputs
    # are keyed by the returned task_id (outputs/<task_id>/), not a user-supplied id.
    paper_path: str
    rubric_path: str | None = None   # omitted -> config default_prompt_path


class GradingTaskCreateResponse(BaseModel):
    task_id: str
    task_type: str
    status: str
    current_step: str
    progress: int
    created_at: str
    log_path: str | None = None


class DirInfo(BaseModel):
    papers_dir: str | None = None
    dir_name: str | None = None
    rubric_path: str | None = None
    rubric_name: str | None = None
    total: int = 0
    completed: int = 0
    failed: int = 0
    pending: int = 0
    current: str | None = None
    last_new_item_at: str | None = None


class GradingTaskStatusResponse(BaseModel):
    task_id: str
    task_type: str
    status: str
    current_step: str
    progress: int
    error_message: str | None = None
    created_at: str
    updated_at: str
    log_path: str | None = None
    dir_info: DirInfo | None = None


class GradingTaskResultResponse(BaseModel):
    task_id: str
    task_type: str
    status: str
    result: dict
    log_path: str | None = None


class GradingTaskControlResponse(BaseModel):
    task_id: str
    task_type: str
    status: str
    current_step: str
    progress: int
    control_action: str | None = None
    updated_at: str
    log_path: str | None = None


class RubricInfo(BaseModel):
    filename: str
    rubric_path: str
    size_bytes: int
    modified_at: str


class RubricListResponse(BaseModel):
    total: int
    rubrics: list[RubricInfo]


class TaskSummary(BaseModel):
    task_id: str
    task_type: str
    status: str
    current_step: str
    progress: int
    error_message: str | None = None
    created_at: str
    updated_at: str
    log_path: str | None = None
    dir_info: DirInfo | None = None


class TaskListResponse(BaseModel):
    total: int
    status_counts: dict[str, int]
    tasks: list[TaskSummary]


class TaskLogResponse(BaseModel):
    task_id: str
    log_path: str | None = None
    lines: list[str]


class TaskSummaryJsonResponse(BaseModel):
    metadata: dict
    students: dict
    updated_at: str | None = None
    student_count: int = 0


class FsEntry(BaseModel):
    name: str
    path: str
    is_dir: bool


class FsListResponse(BaseModel):
    path: str
    parent: str | None = None
    entries: list[FsEntry]


class GradingConfigResponse(BaseModel):
    dpi: int | None = None
    page_columns: int | None = None
    column_split_ratio: float | None = None
    force_split: bool | None = None
    force_split_pairs: list[list[int]] | None = None
    contrast_enhance: bool | None = None
    contrast_factor: float | None = None
    max_tokens: int | None = None
    vlm_temperature: float | None = None
    max_image_pixels: int | None = None
    poll_interval: int | None = None
    stable_checks: int | None = None
    idle_timeout: int | None = None
    min_score: float | None = None
    sort_boxes: bool | None = None
    expand_margin: int | None = None
    merge_overlapping: bool | None = None
    iou_threshold: float | None = None
    vlm_model: str | None = None
    ocr_model: str | None = None
    layout_model: str | None = None


class GradingConfigUpdateRequest(BaseModel):
    dpi: int | None = None
    page_columns: int | None = None
    column_split_ratio: float | None = None
    force_split: bool | None = None
    force_split_pairs: list[list[int]] | None = None
    contrast_enhance: bool | None = None
    contrast_factor: float | None = None
    max_tokens: int | None = None
    vlm_temperature: float | None = None
    max_image_pixels: int | None = None
    poll_interval: int | None = None
    stable_checks: int | None = None
    idle_timeout: int | None = None
    min_score: float | None = None
    sort_boxes: bool | None = None
    expand_margin: int | None = None
    merge_overlapping: bool | None = None
    iou_threshold: float | None = None


class RubricContentResponse(BaseModel):
    filename: str
    content: str


class RubricUpdateRequest(BaseModel):
    content: str


class RubricUpdateResponse(BaseModel):
    filename: str
    size_bytes: int


class UnifiedTaskCreateRequest(BaseModel):
    task_type: str
    payload: dict


class UnifiedTaskCreateResponse(BaseModel):
    task_id: str
    task_type: str
    status: str
    current_step: str
    progress: int
    created_at: str


class UnifiedTaskStatusResponse(BaseModel):
    task_id: str
    task_type: str
    status: str
    current_step: str
    progress: int
    error_message: str | None = None
    created_at: str
    updated_at: str


class UnifiedTaskResultResponse(BaseModel):
    task_id: str
    task_type: str
    status: str
    result: dict


class UnifiedTaskControlResponse(BaseModel):
    task_id: str
    task_type: str
    status: str
    current_step: str
    progress: int
    control_action: str | None = None
    updated_at: str
