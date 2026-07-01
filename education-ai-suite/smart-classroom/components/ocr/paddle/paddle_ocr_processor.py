import os
# PP-OCRv6 PIR models crash paddle's oneDNN executor
os.environ.setdefault("FLAGS_use_mkldnn", "0")
from components.ocr.base_ocr import BaseOCR
from typing import List
import logging
from utils.config_loader import config

logger = logging.getLogger(__name__)


def _patch_paddle_mkldnn():
    """Disable oneDNN in paddle inference to avoid PIR attribute crash."""
    import paddle.inference
    _OrigConfig = paddle.inference.Config

    class _PatchedConfig(_OrigConfig):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.disable_mkldnn()

        def enable_mkldnn(self, *a, **kw):
            pass

    paddle.inference.Config = _PatchedConfig


class PaddleOCRProcessor(BaseOCR):
    _model = None
    _config = None

    def __init__(self, lang=None, use_angle_cls: bool = True, device=None):
        lang = lang or config.app.language
        device = device or config.models.ocr.device
        super().__init__(lang, use_angle_cls, device)

        model_config_key = (use_angle_cls, device)

        if PaddleOCRProcessor._model is None or PaddleOCRProcessor._config != model_config_key:
            logger.info("Loading PaddleOCR model...")
            from paddleocr import PaddleOCR
            _patch_paddle_mkldnn()

            PaddleOCRProcessor._model = PaddleOCR(
                text_detection_model_name=config.models.ocr.det_model,
                text_recognition_model_name=config.models.ocr.rec_model,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=self.use_angle_cls,
                device=self.device.lower(),
            )

            PaddleOCRProcessor._config = model_config_key
            logger.info("Model loaded")

        self.ocr_model = PaddleOCRProcessor._model

    def ocr(self, file_path: str) -> List[List]:
        return self.ocr_model.predict(file_path)

    def extract_text(self, file_path: str) -> str:
        result = self.ocr(file_path)

        if not result:
            return ""
        lines = []
        for item in result:
            rec_texts = getattr(item, "rec_texts", None) or item.get("rec_texts", [])
            lines.extend(rec_texts)

        return "\n".join(lines)
