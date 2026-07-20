from threading import Lock
from typing import Optional
import logging

logger = logging.getLogger(__name__)

try:
    from model_manager.capability.state import CapabilityState
except ImportError:
    from model_manager.capability import CapabilityState


_OCR_MAX_CONCURRENCY = 2   # fallback if config key absent
_OCR_QUEUE_MAX = 16        # fallback if config key absent (design §6.1 default)


def _process_memory_mb() -> Optional[float]:
    """Return process RSS in MB, or None if psutil is unavailable."""
    try:
        import psutil
        return round(psutil.Process().memory_info().rss / 1024 / 1024, 1)
    except Exception:
        return None


class OcrHandler:
    """Owns OCR processor selection, runner wiring, and the extract_text API.

    The processor is loaded lazily on the first call. All calls are routed
    through a CapabilityRunner that enforces the concurrency/queue limits.
    Both ``extract_text`` and ``extract_text_with_scores`` dispatch to the same
    processor through that single runner, so they share one concurrency budget.
    """

    def __init__(self) -> None:
        self._runner = None
        self._processor = None
        self._provider: Optional[str] = None
        self._device: Optional[str] = None
        self._state = CapabilityState.UNLOADED
        self._max_concurrency: int = _OCR_MAX_CONCURRENCY  # updated from config on first load
        self._lock = Lock()

    def extract_text(self, image) -> str:
        return self._get_runner().submit("extract_text", image)

    def extract_text_with_scores(self, image):
        """Return (text, per_line_confidence_scores) for confidence-gated callers."""
        return self._get_runner().submit("extract_text_with_scores", image)

    def load(self) -> None:
        """Force the processor and runner to initialise (warmup)."""
        self._get_runner()

    @property
    def state(self) -> CapabilityState:
        return self._state

    @property
    def loaded(self) -> bool:
        """Alias for ``state == READY``; kept for backward compatibility."""
        return self._state == CapabilityState.READY

    @property
    def provider(self) -> Optional[str]:
        return self._provider

    @property
    def device(self) -> Optional[str]:
        return self._device

    @property
    def max_concurrency(self) -> int:
        return self._max_concurrency

    def memory_stats(self) -> dict:
        """Return process memory stats. Only meaningful when loaded."""
        stats: dict = {}
        rss = _process_memory_mb()
        if rss is not None:
            stats["process_rss_mb"] = rss
        return stats

    def shutdown(self) -> None:
        """Transition READY → EVICTING → UNLOADED and release the runner."""
        with self._lock:
            if self._state == CapabilityState.READY:
                self._state = CapabilityState.EVICTING
            self._runner = None
            self._processor = None
            self._provider = None
            self._device = None
            self._state = CapabilityState.UNLOADED

    # ------------------------------------------------------------------
    # Internal wiring
    # ------------------------------------------------------------------
    def _get_runner(self):
        if self._state == CapabilityState.READY:  # fast path
            return self._runner
        with self._lock:
            if self._runner is None:
                self._state = CapabilityState.LOADING
                try:
                    self._processor = self._build_processor()
                    max_concurrency, queue_max = self._concurrency_config()
                    self._max_concurrency = max_concurrency
                    try:
                        from model_manager.capability.runner import CapabilityRunner
                    except ImportError:
                        from model_manager.capability import CapabilityRunner
                    self._runner = CapabilityRunner(
                        self._call_processor,
                        max_concurrency=max_concurrency,
                        queue_max=queue_max,
                    )
                    self._state = CapabilityState.READY
                except Exception:
                    self._state = CapabilityState.UNLOADED
                    raise
        return self._runner

    def _call_processor(self, method: str, *args, **kwargs):
        """Dispatch a processor call by name so multiple public methods
        (extract_text / extract_text_with_scores) share one runner."""
        return getattr(self._processor, method)(*args, **kwargs)

    def _concurrency_config(self):
        """Return (max_concurrency, queue_max) from config, with fallback to defaults."""
        try:
            from utils.config_loader import config
            return (
                int(getattr(config.models.ocr, "concurrency", _OCR_MAX_CONCURRENCY)),
                int(getattr(config.models.ocr, "queue_max", _OCR_QUEUE_MAX)),
            )
        except Exception:
            return _OCR_MAX_CONCURRENCY, _OCR_QUEUE_MAX

    def _build_processor(self):
        from utils.config_loader import config

        provider = str(config.models.ocr.provider).lower()
        self._provider = provider
        self._device = str(config.models.ocr.device)

        if provider in ("native", "paddle"):
            from components.ocr.paddle.paddle_ocr_processor import PaddleOCRProcessor
            return PaddleOCRProcessor(
                lang=config.app.language,
                use_angle_cls=True,
                device=config.models.ocr.device,
            )
        if provider == "openvino":
            self._ensure_openvino_models(config)
            from components.ocr.openvino.openvino_ocr_processor import OpenVINOOCRProcessor
            return OpenVINOOCRProcessor(
                lang=config.app.language,
                use_angle_cls=True,
                device=config.models.ocr.device,
                ir_models_dir=config.models.ocr.model_dir,
            )
        raise ValueError(f"Unsupported OCR provider: {provider}")

    def _ensure_openvino_models(self, config) -> None:
        """Download and convert OCR ONNX models to OpenVINO IR if not already cached.

        Owns the full model-file lifecycle for the openvino provider so that
        OcrHandler is self-contained — no external ensure_model step required.
        """
        import shutil
        from pathlib import Path
        import openvino as ov
        from paddlex.inference.utils.official_models import official_models

        model_dir = Path(config.models.ocr.model_dir)
        models = [
            ("det", config.models.ocr.det_model),
            ("rec", config.models.ocr.rec_model),
            ("cls", config.models.ocr.cls_model),
        ]

        all_cached = all(
            (model_dir / mtype / mname / "inference.xml").exists()
            for mtype, mname in models
        )
        if all_cached:
            logger.info("OpenVINO IR models already cached, skipping download/conversion")
            return

        core = ov.Core()
        for model_type, model_name in models:
            out_dir = model_dir / model_type / model_name
            ir_path = out_dir / "inference.xml"
            if ir_path.exists():
                continue

            logger.info(f"Downloading {model_name} (ONNX format)...")
            downloaded_dir = Path(
                official_models.get_model_path(model_name, model_formats=["onnx"])
            )
            out_dir.mkdir(parents=True, exist_ok=True)
            onnx_path = downloaded_dir / "inference.onnx"
            yml_src = downloaded_dir / "inference.yml"
            if yml_src.exists():
                shutil.copy2(yml_src, out_dir / "inference.yml")

            logger.info(f"Converting {model_name} ONNX → OpenVINO IR...")
            model = core.read_model(str(onnx_path))
            ov.save_model(model, str(ir_path))
            logger.info(f"Saved: {ir_path}")
