from typing import Optional
from fastapi import Header, UploadFile
from fastapi.responses import JSONResponse
from fastapi import APIRouter, FastAPI, File, HTTPException, status
from dto.transcription_dto import TranscriptionRequest
from dto.summarizer_dto import SummaryRequest
from pipeline import Pipeline
import json, os
from fastapi.responses import StreamingResponse
from utils.runtime_config_loader import RuntimeConfig
from utils.storage_manager import StorageManager
from utils.platform_info import get_platform_and_model_info
from dto.project_settings import ProjectSettings
from monitoring.monitor import start_monitoring, stop_monitoring, get_metrics
from utils.audio_util import save_audio_file
import logging
logger = logging.getLogger(__name__)
router = APIRouter()
router = APIRouter()

@router.get("/health")
def health():
    return JSONResponse(content={"status": "ok"}, status_code=200)

@router.post("/upload-audio")
def upload_audio(file: UploadFile = File(...)):
    status_code = status.HTTP_201_CREATED
    try:
        filename, filepath = save_audio_file(file)
        return JSONResponse(
            status_code=status_code,
            content={
                "filename": filename,
                "message": "File uploaded successfully",
                "path": filepath
            }
        )
    except HTTPException as he:
        logger.error(f"HTTPException occurred: {he.detail}")
        return JSONResponse(
            status_code=he.status_code,
            content={"status": "error", "message": he.detail}
        )
    except Exception as e:
        logger.error(f"General exception occurred: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": "Failed to upload audio file"}
    )


@router.post("/transcribe")
async def transcribe_audio(
    request: TranscriptionRequest,
    x_session_id: Optional[str] = Header(None)
):
    pipeline = Pipeline(x_session_id)
    audio_path = request.audio_filename

    def stream_transcription():
        for chunk_data in pipeline.run_transcription(audio_path):
            yield json.dumps(chunk_data) + "\n"

    response = StreamingResponse(stream_transcription(), media_type="application/json")
    response.headers["X-Session-ID"] = pipeline.session_id
    return response


@router.post("/summarize")
def summarize_audio(request: SummaryRequest):
    pipeline = Pipeline(request.session_id)

    def event_stream():
        for token in pipeline.run_summarizer():
            if token.startswith("[ERROR]:"):
                logger.error(f"Error while summarizing: {token}")
                yield json.dumps({"token": "", "error": token}) + "\n"
                break
            else:
                yield json.dumps({"token": token, "error": ""}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/json")

@router.get("/performance-metrics")
def get_summary_metrics(session_id: Optional[str] = Header(None, alias="session_id")):
    project_config = RuntimeConfig.get_section("Project")
    location = project_config.get("location")
    name = project_config.get("name")

    if not session_id:
        return JSONResponse(
            content={"error": "Missing required header: session_id"},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    if not location or not name:
        return JSONResponse(
            content={"error": "Missing project configuration for 'location' or 'name'"},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    try:
        nested_metrics = StorageManager.read_performance_metrics(location, name, session_id)
        return JSONResponse(
            content=nested_metrics,
            status_code=status.HTTP_200_OK
        )
    except Exception as e:
        logger.error(f"Error reading performance metrics: {e}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@router.get("/project")
def get_project_config():
    return RuntimeConfig.get_section("Project")

@router.post("/project")
def update_project_config(payload: ProjectSettings):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update.")
    return RuntimeConfig.update_section("Project", updates)

@router.post("/start-monitoring")
def start_monitoring_endpoint():
    start_monitoring()
    return JSONResponse(content={"status": "success", "message": "Monitoring started"})

@router.get("/metrics")
def get_metrics_endpoint(x_session_id: Optional[str] = Header(None)):
    if x_session_id is None or "":
        return ""
    project_config = RuntimeConfig.get_section("Project")
    return get_metrics(os.path.join(project_config.get("location"), project_config.get("name"), x_session_id, "utilization_logs"))

@router.get("/platform-info")
def get_platform_info():
    try:
        info = get_platform_and_model_info()
        return JSONResponse(content=info, status_code=200)
    except Exception as e:
        logger.error(f"Error fetching platform info: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

@router.post("/stop-monitoring")
def stop_monitoring_endpoint():
    stop_monitoring()
    return JSONResponse(content={"status": "success", "message": "Monitoring stopped"})

def register_routes(app: FastAPI):
    app.include_router(router)