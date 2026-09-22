"""Chunking and diarization-backend resolution for the audio pipeline.

Kept out of ``utils/config_loader`` because that module is imported by every feature at
startup and must not raise on a transcription-only misconfiguration.
"""
import logging
from typing import Optional

from dto.audiosource import AudioSource
from utils.config_loader import config

logger = logging.getLogger(__name__)

BACKENDS = ("pyannote", "campplus")

# Whole-file processing and the CAM++ backend are only supported on this ASR stack:
# FunASR runs long audio natively, and the CAM++ speaker model is Mandarin-tuned.
FUNASR_PARAFORMER = ("funasr", "paraformer-zh")


def _is_funasr_paraformer() -> bool:
    asr = config.models.asr
    return (str(asr.provider).lower(), str(asr.name).lower()) == FUNASR_PARAFORMER


def _require_funasr_paraformer(key: str, value) -> None:
    if not _is_funasr_paraformer():
        asr = config.models.asr
        raise ValueError(
            f"{key}={value} requires models.asr.provider=funasr and "
            f"models.asr.name=paraformer-zh, got {asr.provider}/{asr.name}."
        )


def resolve_chunking(source_type: Optional[AudioSource] = None) -> bool:
    """True to process audio in chunks, False for a single pass over the whole recording."""
    if config.audio_preprocessing.chunking:
        return True

    if source_type == AudioSource.MICROPHONE:
        logger.warning(
            "audio_preprocessing.chunking=false is not supported for microphone capture "
            "(the recording is not available up front); using chunked processing."
        )
        return True

    _require_funasr_paraformer("audio_preprocessing.chunking", False)
    return False


def resolve_diarization_backend() -> str:
    backend = str(config.models.diarization.backend).lower()
    if backend not in BACKENDS:
        raise ValueError(
            f"Unsupported models.diarization.backend={backend}, "
            f"expected one of {list(BACKENDS)}."
        )
    if backend == "campplus":
        _require_funasr_paraformer("models.diarization.backend", backend)
    return backend
