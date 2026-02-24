from components.asr.base_asr import BaseASR
import soundfile as sf
import librosa
import openvino_genai as ov_genai
import logging
from utils.ensure_model import get_asr_model_path

logger = logging.getLogger(__name__)

class Whisper(BaseASR):
    def __init__(
        self,
        model_name="whisper-small",
        device="CPU",
        revision=None,
        threads_limit=None,
    ):
        logger.info(f"Loading Model: model name={model_name}, device={device}")

        self.model_path = get_asr_model_path()
        config = (
            {"INFERENCE_NUM_THREADS": str(threads_limit)}
            if threads_limit and threads_limit > 0
            else {}
        )

        self.model = ov_genai.WhisperPipeline(
            self.model_path,
            device=device,
            config=config
        )

        # ---- ONLY hardcoded anti-hallucination parameters ----
        self.gen_config = ov_genai.WhisperGenerationConfig(
            return_timestamps=True,
            task="transcribe",
            suppress_tokens=[-1],        # suppress non-speech tokens
            repetition_penalty=1.1,      # reduce repeated words
            presence_penalty=0.0,
            frequency_penalty=0.0,
            logprobs=1                   # computed (not used)
        )

        self.model.set_generation_config(self.gen_config)

        # ---- post-filtering thresholds (hardcoded) ----
        self.min_segment_duration = 0.25
        self.min_words = 2

    def transcribe(self, audio_path: str, temperature: float) -> dict:
        audio, sr = self._load_wav_mono_16k(audio_path)

        # ---- caller can still pass dynamic kwargs via generate() upstream ----
        result = self.model.generate(audio)

        segments = []
        seen_texts = set()

        if hasattr(result, "chunks") and result.chunks:
            for seg in result.chunks:
                start = float(seg.start_ts)
                end = float(seg.end_ts)
                text = seg.text.strip()

                duration = end - start
                word_count = len(text.split())

                # ---- silence & noise filtering ----
                if not text:
                    continue

                if duration < self.min_segment_duration:
                    continue

                if word_count < self.min_words:
                    continue

                # ---- repetition guard ----
                norm = text.lower()
                if norm in seen_texts:
                    continue

                seen_texts.add(norm)

                segments.append({
                    "start": start,
                    "end": end,
                    "text": text
                })

        final_text = " ".join(seg["text"] for seg in segments)

        return {
            "text": final_text,
            "segments": segments
        }

    def _load_wav_mono_16k(self, path):
        audio, sr = sf.read(path, dtype="float32")

        if sr != 16000:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
            sr = 16000

        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        return audio, sr