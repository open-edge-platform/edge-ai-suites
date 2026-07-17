from components.asr_component import ASRComponent
from components.summarizer_component import SummarizerComponent
from utils.config_loader import config
from model_manager import ModelManager
import logging

logger = logging.getLogger(__name__)

def preload_models():
    """Preload models based on config.yaml enabled flags."""
    
    # Build list of enabled capabilities
    enabled_capabilities = []
    
    # Check if OCR is enabled
    if hasattr(config.models, 'ocr') and hasattr(config.models.ocr, 'enabled'):
        if config.models.ocr.enabled:
            enabled_capabilities.append('ocr')
            logger.info("OCR enabled in config")
        else:
            logger.info("OCR disabled in config - skipping")
    
    # ASR is always enabled (check for provider presence)
    if hasattr(config.models, 'asr') and hasattr(config.models.asr, 'provider'):
        if config.models.asr.provider:
            enabled_capabilities.append('asr')
            logger.info("ASR will be loaded (provider configured)")
    
    # Load enabled capabilities via ModelManager
    if enabled_capabilities:
        logger.info(f"Loading capabilities via ModelManager: {enabled_capabilities}")
        mgr = ModelManager.instance()
        mgr.warmup(enabled_capabilities)
        logger.info("ModelManager warmup complete")
    else:
        logger.warning("No capabilities enabled - skipping ModelManager warmup")
    
    # Load summarizer (not yet managed by ModelManager)
    if hasattr(config.models, 'summarizer'):
        logger.info("Loading Summarizer component")
        SummarizerComponent(
            session_id="startup",
            provider=config.models.summarizer.provider,
            model_name=config.models.summarizer.name,
            temperature=config.models.summarizer.temperature,
            device=config.models.summarizer.device
        )
