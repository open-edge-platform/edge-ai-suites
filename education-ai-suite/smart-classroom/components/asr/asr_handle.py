"""
ASR Handler - Manages ASR capability lifecycle and execution.
"""
import logging
from threading import Lock
from typing import Optional

from model_manager.capability.state import CapabilityState
from model_manager.capability.runner import CapabilityRunner
from utils.config_loader import config
from utils.runtime_config_loader import RuntimeConfig

logger = logging.getLogger(__name__)


class AsrHandler:
    """Manages ASR (Automatic Speech Recognition) model loading and inference."""

    def __init__(self):
        self.state = CapabilityState.UNLOADED
        self._processor = None
        self._runner: Optional[CapabilityRunner] = None
        self._lock = Lock()
        
        # Read configuration
        self.provider = config.models.asr.provider if hasattr(config.models, 'asr') else "openai"
        self.device = config.models.asr.device if hasattr(config.models, 'asr') else "CPU"
        self.model_name = config.models.asr.name if hasattr(config.models, 'asr') else "whisper-small"

    @property
    def loaded(self) -> bool:
        """Returns True if the ASR model is loaded and ready."""
        return self.state == CapabilityState.READY

    @property
    def max_concurrency(self) -> int:
        """Returns the configured max concurrency for ASR."""
        if self._runner:
            return self._runner._semaphore._value
        concurrency, _ = self._concurrency_config()
        return concurrency

    def _concurrency_config(self) -> tuple[int, int]:
        """Read max_concurrency and queue_max from runtime config."""
        asr_cfg = RuntimeConfig.get_section("asr")
        max_concurrency = asr_cfg.get("max_concurrency", 1)
        queue_max = asr_cfg.get("queue_max", 8)
        return max_concurrency, queue_max

    def _build_processor(self):
        """Instantiate the ASR processor based on configured provider."""
        from components.asr.openai.whisper import Whisper as OA_Whisper
        from components.asr.openvino.whisper import Whisper as OV_Whisper
        from components.asr.funasr.paraformer import Paraformer

        provider = self.provider.lower()
        model_name = self.model_name.lower()
        device = self.device.lower()

        logger.info(f"Building ASR processor: provider={provider}, model={model_name}, device={device}")

        if provider == "openai" and "whisper" in model_name:
            return OA_Whisper(model_name, device, None)
        elif provider == "openvino" and "whisper" in model_name:
            threads_limit = config.models.asr.threads_limit if hasattr(config.models.asr, 'threads_limit') else None
            return OV_Whisper(model_name, device.upper(), None, threads_limit)
        elif provider == "funasr" and "paraformer" in model_name:
            return Paraformer(model_name, device, None)
        else:
            raise ValueError(f"Unsupported ASR provider/model: {provider}/{model_name}")

    def load(self) -> None:
        """Load the ASR model and transition to READY state."""
        with self._lock:
            if self.state == CapabilityState.READY:
                logger.info("ASR already loaded")
                return

            self.state = CapabilityState.LOADING
            try:
                logger.info("Loading ASR model...")
                self._processor = self._build_processor()
                
                max_concurrency, queue_max = self._concurrency_config()
                self._runner = CapabilityRunner(
                    self._processor.transcribe,
                    max_concurrency=max_concurrency,
                    queue_max=queue_max
                )
                
                self.state = CapabilityState.READY
                logger.info(f"ASR loaded successfully (concurrency={max_concurrency}, queue={queue_max})")
            except Exception as e:
                logger.error(f"Failed to load ASR: {e}")
                self.state = CapabilityState.UNLOADED
                self._processor = None
                self._runner = None
                raise

    def transcribe(self, audio_path: str) -> str:
        if not self.loaded:
            raise RuntimeError("ASR not loaded. Call load() first.")
        
        return self._runner.submit(audio_path)

    def shutdown(self) -> None:
        """Unload the ASR model and release resources."""
        with self._lock:
            if self.state == CapabilityState.UNLOADED:
                return

            logger.info("Shutting down ASR...")
            self._processor = None
            self._runner = None
            self.state = CapabilityState.UNLOADED
            logger.info("ASR shutdown complete")

    def memory_stats(self) -> dict:
        """Return memory statistics for the loaded ASR model."""
        import psutil
        process = psutil.Process()
        mem_info = process.memory_info()
        return {
            "process_rss_mb": mem_info.rss / 1024 / 1024,
            "process_vms_mb": mem_info.vms / 1024 / 1024,
        }
