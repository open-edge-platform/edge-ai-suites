from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile

from kiosk_core.api.endpoints import router as api_router
from kiosk_core.models import FileSessionStartRequest, SessionStartRequest, SessionStopResponse
from kiosk_core.service import SessionService


app = FastAPI(title="kiosk-core")
service = SessionService()
app.include_router(api_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/devices")
def list_devices() -> dict[str, list[dict[str, str | int]]]:
    return {"devices": service.list_input_devices()}


@app.get("/api/v1/sessions")
def list_sessions() -> dict[str, list[dict[str, object]]]:
    return {"sessions": service.list_sessions()}


@app.get("/api/v1/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, object]:
    try:
        return service.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/v1/sessions/start-stream")
def start_stream_session(request: SessionStartRequest) -> dict[str, object]:
    """Open a browser streaming session.  The caller then pushes audio chunks
    via POST /api/v1/sessions/{session_id}/audio and signals end-of-stream
    via POST /api/v1/sessions/{session_id}/audio/end."""
    try:
        return service.start_stream_session(request)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/v1/sessions/{session_id}/audio")
async def push_audio_chunk(session_id: str, request: Request) -> dict[str, str]:
    """Push a raw 16-bit mono PCM WAV chunk into an active browser stream session."""
    wav_bytes = await request.body()
    if not wav_bytes:
        raise HTTPException(status_code=400, detail="Empty audio body")
    try:
        service.push_audio_chunk(session_id, wav_bytes)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "accepted"}


@app.post("/api/v1/sessions/{session_id}/audio/end")
def end_audio_stream(session_id: str) -> dict[str, str]:
    """Signal end-of-stream so the session can finalise and run RAG+TTS."""
    try:
        service.signal_stream_end(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "eos_accepted"}


@app.post("/api/v1/sessions/start", response_model=None)
def start_session(request: SessionStartRequest) -> dict[str, object]:
    try:
        return service.start_session(request)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/v1/sessions/start-file")
def start_file_session(
    file: UploadFile = File(...),
    device: int | str | None = Form(None),
    sample_rate: int = Form(16000),
    chunk_seconds: float = Form(4.0),
    silence_timeout_seconds: float = Form(1.5),
    max_session_seconds: float = Form(20.0),
    silence_threshold: int = Form(900),
    language: str | None = Form(None),
    temperature: float = Form(0.0),
    analyzer_url: str = Form("http://127.0.0.1:8010/v1/audio/transcriptions"),
    rag_url: str = Form("http://127.0.0.1:8020/api/v1/query"),
    tts_url: str = Form("http://127.0.0.1:8011/v1/audio/speech"),
    tts_model: str = Form("qwen-tts"),
    tts_voice: str | None = Form(None),
    tts_language: str | None = Form("English"),
    tts_instructions: str | None = Form(None),
    realtime_factor: float = Form(1.0),
    include_sources: bool = Form(False),
    include_performance_metrics: bool = Form(True),
    include_llm_metrics: bool = Form(True),
) -> dict[str, object]:
    request = FileSessionStartRequest(
        device=device,
        sample_rate=sample_rate,
        chunk_seconds=chunk_seconds,
        silence_timeout_seconds=silence_timeout_seconds,
        max_session_seconds=max_session_seconds,
        silence_threshold=silence_threshold,
        language=language,
        temperature=temperature,
        analyzer_url=analyzer_url,
        rag_url=rag_url,
        tts_url=tts_url,
        tts_model=tts_model,
        tts_voice=tts_voice,
        tts_language=tts_language,
        tts_instructions=tts_instructions,
        realtime_factor=realtime_factor,
        include_sources=include_sources,
        include_performance_metrics=include_performance_metrics,
        include_llm_metrics=include_llm_metrics,
    )
    try:
        return service.start_file_session(request, file)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/v1/sessions/{session_id}/stop", response_model=SessionStopResponse)
def stop_session(session_id: str) -> SessionStopResponse:
    try:
        return service.stop_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8012, reload=False)
