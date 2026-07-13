from datetime import datetime

from pydantic import BaseModel, Field

from kiosk_core import config


class SessionStartRequest(BaseModel):
    device: int | str | None = None
    sample_rate: int = Field(default=config.DEFAULT_SAMPLE_RATE, ge=8000, le=48000)
    chunk_seconds: float = Field(default=config.DEFAULT_CHUNK_SECONDS, gt=0.5, le=30)
    silence_timeout_seconds: float = Field(
        default=config.DEFAULT_SILENCE_TIMEOUT_SECONDS,
        gt=0.2,
        le=10,
    )
    max_session_seconds: float = Field(default=config.DEFAULT_MAX_SESSION_SECONDS, gt=1, le=300)
    silence_threshold: int = Field(default=config.DEFAULT_SILENCE_THRESHOLD, ge=1, le=32767)
    language: str | None = None
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    analyzer_url: str = config.DEFAULT_ANALYZER_URL
    rag_url: str = config.DEFAULT_RAG_URL
    tts_url: str = config.DEFAULT_TTS_URL
    tts_model: str = config.DEFAULT_TTS_MODEL
    tts_voice: str | None = config.DEFAULT_TTS_VOICE
    tts_language: str | None = config.DEFAULT_TTS_LANGUAGE
    tts_instructions: str | None = config.DEFAULT_TTS_INSTRUCTIONS
    # Recent conversation turns prior to this question, oldest-first.
    # Forwarded verbatim to the RAG service so follow-ups have context.
    history: list[dict[str, str]] = Field(default_factory=list)
    include_sources: bool = False
    include_performance_metrics: bool = True
    include_llm_metrics: bool = True


class FileSessionStartRequest(SessionStartRequest):
    realtime_factor: float = Field(default=1.0, gt=0.0, le=100.0)


class SessionStopResponse(BaseModel):
    session_id: str
    status: str
    stop_requested_at: datetime
