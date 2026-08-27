from fastapi import APIRouter, HTTPException

from api.v1.schemas.session import (
    DeleteResponse,
    ProcessResponse,
    SessionListResponse,
    StatusResponse,
    WorkflowRequest,
)
from services import session_service
from services.session_service import (
    SessionNotFound,
    SessionRunning,
    SessionValidationError,
)

router = APIRouter()


@router.get("", response_model=SessionListResponse)
def list_sessions():
    return session_service.list_sessions()


@router.post("/process", response_model=ProcessResponse)
def process_session(req: WorkflowRequest):
    try:
        return session_service.create_process(req)
    except SessionValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
