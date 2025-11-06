import asyncio
from typing import Optional
from fastapi import Header, UploadFile
from fastapi.responses import JSONResponse
from fastapi import APIRouter, FastAPI, File, HTTPException, status
from dto.transcription_dto import TranscriptionRequest
from dto.summarizer_dto import SummaryRequest
from dto.video_analytics_dto import VideoAnalyticsRequest
from pipeline import Pipeline
import json, os
from fastapi.responses import StreamingResponse
from utils.runtime_config_loader import RuntimeConfig
from utils.storage_manager import StorageManager
from utils.platform_info import get_platform_and_model_info
from dto.project_settings import ProjectSettings
from monitoring.monitor import start_monitoring, stop_monitoring, get_metrics
from utils.audio_util import save_audio_file
from utils.locks import audio_pipeline_lock, video_analytics_lock
from components.va.va_pipeline_service import VideoAnalyticsPipelineService, PipelineOptions
import logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/health")
def health():
    return JSONResponse(content={"status": "ok"}, status_code=200)

@router.post("/upload-audio")
def upload_audio(file: UploadFile = File(...)):
    status_code = status.HTTP_201_CREATED
    
    if audio_pipeline_lock.locked():
        raise HTTPException(status_code=429, detail="Session Active, Try Later")
    
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
def transcribe_audio(
    request: TranscriptionRequest,
    x_session_id: Optional[str] = Header(None)
):
    
    if audio_pipeline_lock.locked():
        raise HTTPException(status_code=429, detail="Session Active, Try Later")
    
    pipeline = Pipeline(x_session_id)
    audio_path = request.audio_filename
    
    def stream_transcription():
        for chunk_data in pipeline.run_transcription(audio_path):
            yield json.dumps(chunk_data) + "\n"
                

    response = StreamingResponse(stream_transcription(), media_type="application/json")
    response.headers["X-Session-ID"] = pipeline.session_id
    return response


@router.post("/summarize")
async def summarize_audio(request: SummaryRequest):
    if audio_pipeline_lock.locked():
        raise HTTPException(status_code=429, detail="Session Active, Try Later")
    
    pipeline = Pipeline(request.session_id)
    
    async def event_stream():
        for token in pipeline.run_summarizer():
            if token.startswith("[ERROR]:"):
                logger.error(f"Error while summarizing: {token}")
                yield json.dumps({"token": "", "error": token}) + "\n"
                break
            else:
                yield json.dumps({"token": token, "error": ""}) + "\n"
            await asyncio.sleep(0)

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

# Global video analytics service instances per session
va_services = {}  # {session_id: VideoAnalyticsPipelineService}

@router.post("/start-video-analytics-pipeline")
def start_video_analytics_pipeline(
    request: VideoAnalyticsRequest, x_session_id: Optional[str] = Header(None)
):
    """
    Start video analytics pipeline

    Args:
        request: VideoAnalyticsRequest with pipeline_name, source

    Returns:
        JSON with HLS stream address
    """
    if not x_session_id:
        raise HTTPException(
            status_code=400, detail="Missing required header: x-session-id"
        )

    # Validate pipeline name
    valid_pipelines = ["front", "back", "content"]
    if request.pipeline_name not in valid_pipelines:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid pipeline_name. Must be one of: {valid_pipelines}",
        )

    # Check if a video analytics pipeline is already running for this session
    with video_analytics_lock:
        if x_session_id in va_services:
            existing_service = va_services[x_session_id]
            if existing_service.is_pipeline_running(request.pipeline_name):
                raise HTTPException(
                    status_code=409,
                    detail=f"Pipeline '{request.pipeline_name}' already running for session {x_session_id}",
                )

        try:
            # Create or get service for this session
            if x_session_id not in va_services:
                project_config = RuntimeConfig.get_section("Project")
                location = project_config.get("location", "outputs")
                name = project_config.get("name", "default")

                output_dir = os.path.join(location, name, x_session_id, "va")
                os.makedirs(output_dir, exist_ok=True)

                va_services[x_session_id] = VideoAnalyticsPipelineService()

            service = va_services[x_session_id]

            # Prepare pipeline options
            project_config = RuntimeConfig.get_section("Project")
            location = project_config.get("location", "outputs")
            name = project_config.get("name", "default")
            output_dir = os.path.join(location, name, x_session_id, "va")

            options = PipelineOptions(
                output_dir=output_dir,
                output_rtsp="rtsp://127.0.0.1:8554",
            )

            # Launch pipeline
            success = service.launch_pipeline(
                pipeline_name=request.pipeline_name,
                source=request.source,
                options=options,
            )

            if not success:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to start pipeline '{request.pipeline_name}'",
                )

            hls_base_url = "http://localhost:8888"
            response_data = {
                "status": "success",
                "pipeline_name": request.pipeline_name,
                "session_id": x_session_id,
                "hls_stream": f"{hls_base_url}/{request.pipeline_name}_stream",
            }

            return JSONResponse(content=response_data, status_code=200)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error starting video analytics pipeline: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop-video-analytics-pipeline")
def stop_video_analytics_pipeline(
    request: VideoAnalyticsRequest, x_session_id: Optional[str] = Header(None)
):
    """
    Stop video analytics pipeline

    Args:
        request: VideoAnalyticsRequest with pipeline_name

    Returns:
        JSON with status message
    """
    if not x_session_id:
        raise HTTPException(
            status_code=400, detail="Missing required header: x-session-id"
        )

    # Validate pipeline name
    valid_pipelines = ["front", "back", "content"]
    if request.pipeline_name not in valid_pipelines:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid pipeline_name. Must be one of: {valid_pipelines}",
        )

    if x_session_id not in va_services:
        raise HTTPException(
            status_code=404,
            detail=f"No video analytics service found for session {x_session_id}",
        )

    with video_analytics_lock:
        try:
            service = va_services[x_session_id]

            # Check if pipeline is running
            if not service.is_pipeline_running(request.pipeline_name):
                raise HTTPException(
                    status_code=404,
                    detail=f"Pipeline '{request.pipeline_name}' is not running for session {x_session_id}",
                )

            # Stop the pipeline
            success = service.stop_pipeline(request.pipeline_name)

            if not success:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to stop pipeline '{request.pipeline_name}'",
                )

            return JSONResponse(
                content={
                    "status": "success",
                    "pipeline_name": request.pipeline_name,
                    "session_id": x_session_id,
                },
                status_code=200,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error stopping video analytics pipeline: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/stream-content-classification")
def stream_content_classification(x_session_id: Optional[str] = Header(None)):
    """
    Stream content classification results from content pipeline

    Returns:
        JSON stream with content classification data
    """
    if not x_session_id:
        raise HTTPException(
            status_code=400, detail="Missing required header: x_session_id"
        )

    if x_session_id not in va_services:
        raise HTTPException(
            status_code=404,
            detail=f"No video analytics service found for session {x_session_id}",
        )

    service = va_services[x_session_id]

    if not service.is_pipeline_running("content"):
        raise HTTPException(status_code=404, detail="Content pipeline is not running")

    def event_stream():
        try:
            for json_data in service.monitor_pipeline("content", "content_results.txt"):
                objects = json_data.get("objects", [])
                if objects:
                    # Get the first classification result
                    yield json.dumps(
                        objects[0]["classification_layer_name:output"]
                    ) + "\n"
        except Exception as e:
            logger.error(f"Error streaming content classification: {e}")
            yield json.dumps({"error": str(e)}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/json")


@router.get("/class-statistics")
def get_class_statistics(x_session_id: Optional[str] = Header(None)):
    """
    Get class statistics after class

    Returns:
        JSON statistics data
    """
    if not x_session_id:
        raise HTTPException(
            status_code=400, detail="Missing required header: x-session-id"
        )

    if x_session_id not in va_services:
        raise HTTPException(
            status_code=404,
            detail=f"No video analytics service found for session {x_session_id}",
        )

    try:
        service = va_services[x_session_id]

        # Get the front_posture.txt file path
        project_config = RuntimeConfig.get_section("Project")
        location = project_config.get("location", "outputs")
        name = project_config.get("name", "default")
        output_dir = os.path.join(location, name, x_session_id, "va")
        front_posture_file = os.path.join(output_dir, "front_posture.txt")

        # Get pose statistics
        stats = service.get_pose_stats(front_posture_file)

        return JSONResponse(content=stats, status_code=200)

    except Exception as e:
        logger.error(f"Error getting class statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def register_routes(app: FastAPI):
    app.include_router(router)
