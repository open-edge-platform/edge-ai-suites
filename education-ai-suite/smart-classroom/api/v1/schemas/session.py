from typing import Literal

from pydantic import BaseModel


class WorkflowRequest(BaseModel):
    stages: list[str]
    audio_path: str | None = None
    video_sources: dict[str, str] | None = None


class RegisterRequest(BaseModel):
    """A session the caller drives stage by stage, as opposed to WorkflowRequest,
    which hands the whole run to the orchestrator."""

    session_id: str
    stages: list[str]
    audio_path: str | None = None
    video_sources: dict[str, str] | None = None


class RegisterResponse(BaseModel):
    session_id: str
    state: str | None = None
    stages: dict | None = None
    output_dir: str | None = None
    started_at: str | None = None
    # True when the session was already on file and this call changed nothing.
    already_registered: bool = False


class FinalizeRequest(BaseModel):
    # "aborted" is what the browser's unload beacon sends: the page went away
    # mid-run, so the session is over but it did not succeed.
    outcome: Literal["completed", "aborted", "failed"] = "completed"
    error: str | None = None


class FinalizeResponse(BaseModel):
    session_id: str
    state: str | None = None
    error: str | None = None


class SessionSummary(BaseModel):
    session_id: str | None = None
    state: str | None = None
    current_stage: str | None = None
    stages: dict | None = None
    sources: dict | None = None
    error: str | None = None
    started_at: str | None = None
    updated_at: str | None = None


class SessionListResponse(BaseModel):
    # The whole table, not the page — the history screen pages through it.
    total: int
    sessions: list[SessionSummary]


class StageEvent(BaseModel):
    session_id: str | None = None
    stage: str | None = None
    status: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    duration_sec: float | None = None
    error_class: str | None = None
    error_detail: str | None = None


class StageEventsResponse(BaseModel):
    session_id: str
    events: list[StageEvent]


class SessionArtifact(BaseModel):
    stage: str
    kind: Literal["transcript", "markdown", "mindmap", "topics", "stats"]
    filename: str
    size_bytes: int


class ArtifactListResponse(BaseModel):
    session_id: str
    # Only the artifacts that exist; a stage that never ran contributes nothing.
    artifacts: list[SessionArtifact]


class ArtifactTextResponse(SessionArtifact):
    session_id: str
    content: str
    # True when the file was longer than the preview will hand back in one go.
    truncated: bool = False


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
