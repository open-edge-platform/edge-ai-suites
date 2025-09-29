from components.asr_component import ASRComponent
from components.summarizer_component import SummarizerComponent
from utils.config_loader import config

def preload_models():
    # Preload default models
    ASRComponent(session_id="startup", provider=config.models.asr.provider, model_name=config.models.asr.name,device=config.models.asr.device)
    SummarizerComponent(session_id="startup", provider=config.models.summarizer.provider, model_name=config.models.summarizer.name, temperature=config.models.summarizer.temperature, device=config.models.summarizer.device)
