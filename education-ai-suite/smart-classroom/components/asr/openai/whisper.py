from components.asr.base_asr import BaseASR
import whisper
import logging

logger = logging.getLogger(__name__)
 
 
WHISPER_MODEL_MAP = {
    "whisper-tiny": "tiny",
    "whisper-base": "base",
    "whisper-small": "small",
    "whisper-medium": "medium"
}    
 
class Whisper(BaseASR):
   def __init__(self, model_name="whisper-small", device="cpu", revision=None):
        model = WHISPER_MODEL_MAP[model_name] if model_name in WHISPER_MODEL_MAP else (_ for _ in ()).throw(ValueError("Invalid ASR model name"))
        logger.info(f"Loading Model: model name={model_name}, device={device}")
        self.model = whisper.load_model(model)
 
   def transcribe(self, audio_path: str, temperature: float) -> str:
        return self.model.transcribe(audio_path, temperature=temperature)["text"]