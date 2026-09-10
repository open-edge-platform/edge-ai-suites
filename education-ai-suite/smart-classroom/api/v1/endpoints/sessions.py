from fastapi import APIRouter, HTTPException

from api.v1.schemas.session import (
    CancelResponse,
    DeleteResponse,
    FinalizeRequest,
    FinalizeResponse,
    ProcessResponse,
    RegisterRequest,
    RegisterResponse,
    SessionListResponse,
    StatusResponse,
    WorkflowRequest,
)
from services import session_service
from services.session_service import (
    ConcurrencyLimitError,
    SessionNotCancellable,
    SessionNotFound,
    SessionNotRunning,
    SessionRunning,
    SessionValidationError,
)

router = APIRouter()


@router.get("", response_model=SessionListResponse)
def list_sessions():
    return session_service.list_sessions()


@router.get("/running", response_model=SessionListResponse)
def list_running_sessions():
    return session_service.list_running_sessions()


@router.post("/process", response_model=ProcessResponse)
def process_session(req: WorkflowRequest):
    try:
        return session_service.create_process(req)
    except SessionValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConcurrencyLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))


@router.post("/register", response_model=RegisterResponse)
def register_session(req: RegisterRequest):
    """Put a caller-driven session on the books without starting anything."""
    try:
        return session_service.register_session(req)
    except SessionValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{session_id}/finalize", response_model=FinalizeResponse)
def finalize_session(session_id: str, req: FinalizeRequest):
    try:
        return session_service.finalize_session(session_id, req.outcome, req.error)
    except SessionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SessionRunning as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/{session_id}/status", response_model=StatusResponse)
def get_session_progress(session_id: str):
    try:
        return session_service.get_status(session_id)
    except SessionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{session_id}", response_model=DeleteResponse)
def delete_session(session_id: str):
    try:
        return session_service.delete_session(session_id)
    except SessionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SessionRunning as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{session_id}/cancel", response_model=CancelResponse)
def cancel_session(session_id: str):
    try:
        return session_service.cancel_session(session_id)
    except SessionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SessionNotRunning as e:
        raise HTTPException(status_code=409, detail=str(e))
    except SessionNotCancellable as e:
        raise HTTPException(status_code=409, detail=str(e))
