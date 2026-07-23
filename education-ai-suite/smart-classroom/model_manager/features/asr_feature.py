import json
import logging
import re
import subprocess
from typing import Dict, List, Optional

from fastapi import APIRouter, File, Header, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse, StreamingResponse

from components.ffmpeg import audio_preprocessing
from dto.transcription_dto import TranscriptionRequest
from pipeline import Pipeline
from utils.audio_util import save_audio_file
from utils.locks import audio_pipeline_lock

logger = logging.getLogger(__name__)

router = APIRouter()


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

    def stream_transcription():
        for chunk_data in pipeline.run_transcription(request):
            yield json.dumps(chunk_data) + "\n"

    response = StreamingResponse(stream_transcription(), media_type="application/json")
    response.headers["X-Session-ID"] = pipeline.session_id
    return response


@router.get("/devices")
def list_audio_devices():
    result = subprocess.run(
        ["ffmpeg", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    audio_devices = re.findall(r'"(.*?)"\s*\(audio\)', result.stderr)
    formatted_devices = [f"audio={d}" for d in audio_devices]
    return {"devices": formatted_devices}


@router.post("/stop-mic")
def stop_microphone(session_id: str):
    process = audio_preprocessing.FFMPEG_PROCESSES.pop(session_id, None)
    if process:
        logger.info(f"Stopping microphone recording for session {session_id}...")
        process.terminate()
        process.wait(timeout=5)
        return {"status": "stopped", "message": f"Microphone for session {session_id} stopped successfully."}
    else:
        return {"status": "idle", "message": f"No active microphone session found for {session_id}."}


class ASRFeature:
    """F1 live transcription exposed as a FeatureModule."""

    id: str = "asr"
    requires: List[str] = ["asr"]
    depends_on: List[str] = []
    router: APIRouter = router

    def __init__(self) -> None:
        self._handle = None

    def build(self) -> None:
        """Acquire the ASR capability handle from the ModelManager."""
        from model_manager import ModelManager
        self._handle = ModelManager.instance().asr()
        logger.info("ASRFeature built; ASR handle acquired from ModelManager.")

    def teardown(self) -> None:

        self._handle = None
        logger.info("ASRFeature torn down; ASR handle reference released.")

    def ui_descriptor(self) -> Dict:
        return {
            "id": self.id,
            "endpoints": {
                "upload_audio": "/upload-audio",
                "transcribe": "/transcribe",
                "devices": "/devices",
                "stop_mic": "/stop-mic",
            },
        }
