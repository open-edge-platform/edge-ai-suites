from components.asr_component import ASRComponent
from components.summarizer_component import SummarizerComponent
from utils.config_loader import config

def preload_models():
    # Preload default models
    ASRComponent(session_id="startup", provider=config.models.asr.provider, model_name=config.models.asr.name,device=config.models.asr.device)
    SummarizerComponent(session_id="startup", provider=config.models.summarizer.provider, model_name=config.models.summarizer.name, temperature=config.models.summarizer.temperature, device=config.models.summarizer.device)
    
    # OCR warmup has moved to ModelManager.warmup(["ocr"]) called in main.py.
    # The OCRComponent preload below is intentionally removed — the Hub owns
    # the single warm OCR instance and respects config.models.ocr.concurrency /
    # queue_max.  Do not re-add direct OCRComponent construction here.
