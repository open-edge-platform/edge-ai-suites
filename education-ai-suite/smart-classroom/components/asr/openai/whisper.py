from components.asr.base_asr import BaseASR
import whisper
import logging
from utils.config_loader import config
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

WHISPER_MODEL_MAP = {
    "whisper-tiny": "tiny",
    "whisper-base": "base",
    "whisper-small": "small",
    "whisper-medium": "medium",
    "whisper-large": "large-v3",
}


class Whisper(BaseASR):
    """
    Robust Whisper ASR with silence-safe filtering.
    Prevents hallucinations without dropping real speech.
    """

    def __init__(self, model_name="whisper-small", device="cpu", revision=None):
        if model_name not in WHISPER_MODEL_MAP:
            raise ValueError(f"Invalid ASR model name: {model_name}")

        model_id = WHISPER_MODEL_MAP[model_name]
        logger.info(f"Loading Whisper model={model_id} on device={device}")

        self.model = whisper.load_model(model_id, device=device)

        # ---- Conservative thresholds (DO NOT overtune) ----
        self.NO_SPEECH_THRESHOLD = config.models.asr.no_speech_threshold
        self.LOGPROB_THRESHOLD = config.models.asr.logprob_threshold
        self.MIN_DURATION_SEC = config.models.asr.min_duration_sec
        self.MIN_WORDS = config.models.asr.min_words

    def _is_silent_segment(self, seg: Dict[str, Any]) -> bool:
        """
        Decide whether a segment is silence / hallucination.
        Uses MULTIPLE signals to avoid dropping real speech.
        """

        text = seg.get("text", "").strip()
        duration = float(seg["end"]) - float(seg["start"])
        no_speech_prob = seg.get("no_speech_prob", 0.0)
        avg_logprob = seg.get("avg_logprob", 0.0)

        # 1. Must be acoustically silence-like
        if no_speech_prob <= self.NO_SPEECH_THRESHOLD:
            return False

        # 2. Must be low confidence
        if avg_logprob >= self.LOGPROB_THRESHOLD:
            return False

        # 3. Must be very short or nearly empty
        if duration >= self.MIN_DURATION_SEC and len(text.split()) >= self.MIN_WORDS:
            return False

        return True

    def transcribe(self, audio_path: str, temperature: float = 0.0) -> Dict[str, Any]:
        """
        Transcribe audio with strong silence suppression and zero speech loss.
        """

        result = self.model.transcribe(
            audio_path,
            temperature=temperature,
            language="en",
            condition_on_previous_text=False,
            no_speech_threshold=self.NO_SPEECH_THRESHOLD,
            logprob_threshold=self.LOGPROB_THRESHOLD,
            compression_ratio_threshold=2.4,
            verbose=False,
        )

        kept_segments: List[Dict[str, Any]] = []
        dropped = 0

        for seg in result.get("segments", []):
            if self._is_silent_segment(seg):
                dropped += 1
                continue

            kept_segments.append({
                "start": float(seg["start"]),
                "end": float(seg["end"]),
                "text": seg["text"].strip(),
            })

        final_text = " ".join(s["text"] for s in kept_segments).strip()

        return {
            "text": final_text,
            "segments": kept_segments,
            "meta": {
                "model": WHISPER_MODEL_MAP.get("model_name", "unknown"),
                "temperature": temperature,
                "segments_total": len(result.get("segments", [])),
                "segments_kept": len(kept_segments),
                "segments_dropped": dropped,
            },
        }
