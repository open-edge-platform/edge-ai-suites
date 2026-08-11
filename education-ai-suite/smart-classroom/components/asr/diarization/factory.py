import logging

from utils.config_loader import config
from utils.pipeline_modes import resolve_diarization_backend

logger = logging.getLogger(__name__)


def build_diarizer():
    """Instantiate the configured diarization backend. Backends are imported lazily
    because each pulls in a different heavy dependency."""
    backend = resolve_diarization_backend()
    logger.info(f"Building {backend} diarizer")

    if backend == "campplus":
        from components.asr.diarization.campplus_diarizer import CamPlusPlusDiarizer
        return CamPlusPlusDiarizer()

    from components.asr.diarization.pyannote_diarizer import PyannoteDiarizer
    return PyannoteDiarizer(hf_token=config.models.asr.hf_token)
