from utils.config_loader import config
from model_manager import ModelManager
import logging

logger = logging.getLogger(__name__)


def preload_models():
    """Preload models at startup."""
    
    registry = getattr(config.models, "capability_registry", None) or []
    to_warm = [
        capability
        for capability in registry
        if getattr(config.models, capability, None) is not None
        and getattr(getattr(config.models, capability), "enabled", True)
    ]

    if (
        hasattr(config.models, "asr")
        and getattr(config.models.asr, "provider", None)
        and "asr" not in to_warm
    ):
        to_warm.append("asr")

    if to_warm:
        logger.info(f"Warming ModelManager capabilities: {to_warm}")
        ModelManager.instance().warmup(to_warm)
        logger.info("ModelManager warmup complete")
    else:
        logger.warning("No capabilities enabled - skipping ModelManager warmup")
