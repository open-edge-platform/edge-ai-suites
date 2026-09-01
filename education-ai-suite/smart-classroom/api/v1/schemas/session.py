from pydantic import BaseModel


class WorkflowRequest(BaseModel):
    stages: list[str]
    audio_path: str | None = None
    video_sources: dict[str, str] | None = None


class SessionSummary(BaseModel):
    session_id: str | None = None
    state: str | None = None
    current_stage: str | None = None
    stages: dict | None = None
    sources: dict | None = None
    started_at: str | None = None
    updated_at: str | None = None


class SessionListResponse(BaseModel):
    total: int
    sessions: list[SessionSummary]


class ProcessResponse(BaseModel):
    session_id: str
    stages: dict | list | None = None
    output_dir: str | None = None
    started_at: str | None = None


class StatusResponse(BaseModel):
    session_id: str | None = None
    state: str | None = None
    current_stage: str | None = None
    stages: dict | None = None
    sources: dict | None = None
    output_dir: str | None = None
    error: str | None = None
    started_at: str | None = None
    updated_at: str | None = None


class DeleteResponse(BaseModel):
    session_id: str
    deleted: bool
    files_removed: bool


class CancelResponse(BaseModel):
    session_id: str
    cancelled: bool
