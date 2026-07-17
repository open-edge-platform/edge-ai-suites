from threading import Lock
from typing import Optional


class ModelManager:
    _instance: Optional["ModelManager"] = None
    _lock = Lock()

    def __new__(cls) -> "ModelManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        with type(self)._lock:
            if getattr(self, "_initialized", False):
                return
            self._ocr_handler = None
            self._ocr_lock = Lock()
            self._asr_handler = None
            self._asr_lock = Lock()
            self._initialized = True

    @classmethod
    def instance(cls) -> "ModelManager":
        return cls()

    def text_gen(self):
        raise NotImplementedError

    def ocr(self):
        """Return the OcrHandler backed by the configured processor."""
        return self._get_ocr_handler()

    def ocr_vlm(self):
        raise NotImplementedError

    def asr(self):
        """Return the AsrHandler backed by the configured processor."""
        return self._get_asr_handler()

    def warmup(self, capabilities: list[str]) -> None:
        for capability in capabilities or []:
            if capability == "ocr":
                self._get_ocr_handler().load()
            elif capability == "asr":
                self._get_asr_handler().load()

    def health(self) -> dict:
        h = self._ocr_handler
        ocr_health = {
            "state": h.state.value if h else "unloaded",
            "loaded": h.loaded if h else False,
            "provider": h.provider if h else None,
            "device": h.device if h else None,
            "max_concurrency": h.max_concurrency if h else 2,
        }
        if h and h.loaded:
            ocr_health["memory"] = h.memory_stats()
        
        a = self._asr_handler
        asr_health = {
            "state": a.state.value if a else "unloaded",
            "loaded": a.loaded if a else False,
            "provider": a.provider if a else None,
            "device": a.device if a else None,
            "max_concurrency": a.max_concurrency if a else 1,
        }
        if a and a.loaded:
            asr_health["memory"] = a.memory_stats()
        
        return {"ocr": ocr_health, "asr": asr_health}

    def shutdown(self) -> None:
        with self._ocr_lock:
            if self._ocr_handler is not None:
                self._ocr_handler.shutdown()
            self._ocr_handler = None
        
        with self._asr_lock:
            if self._asr_handler is not None:
                self._asr_handler.shutdown()
            self._asr_handler = None

    def _get_ocr_handler(self):
        if self._ocr_handler is not None:
            return self._ocr_handler
        with self._ocr_lock:
            if self._ocr_handler is None:
                from components.ocr.ocr_handle import OcrHandler
                self._ocr_handler = OcrHandler()
        return self._ocr_handler

    def _get_asr_handler(self):
        if self._asr_handler is not None:
            return self._asr_handler
        with self._asr_lock:
            if self._asr_handler is None:
                from components.asr.asr_handle import AsrHandler
                self._asr_handler = AsrHandler()
        return self._asr_handler
