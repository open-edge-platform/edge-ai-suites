import os 
from components.ocr.base_ocr import BaseOCR
from typing import List
import logging
from pathlib import Path
from utils.config_loader import config

logger = logging.getLogger(__name__)


class PaddleOCRProcessor(BaseOCR):
    _model = None
    _config = None

    def __init__(self, lang=None, use_angle_cls: bool = True, device=None):
        lang = lang or config.app.language
        device = device or config.models.ocr.device
        super().__init__(lang, use_angle_cls, device)

        model_config_key = (lang, use_angle_cls, device)

        if PaddleOCRProcessor._model is None or PaddleOCRProcessor._config != model_config_key:
            logger.info("Loading PaddleOCR model...")
            from paddleocr import PaddleOCR  
            det_model = config.models.ocr.det_model
            rec_model = config.models.ocr.rec_model
            cls_model = config.models.ocr.cls_model
             
            models_ocr_paddle = Path(config.models.ocr.model_dir)
            
            det_model_dir = str(models_ocr_paddle / "det" / self.lang / det_model)
            rec_model_dir = str(models_ocr_paddle / "rec" / self.lang / rec_model)
            cls_model_dir = str(models_ocr_paddle / "cls" / self.lang / cls_model) if self.use_angle_cls else None

            PaddleOCRProcessor._model = PaddleOCR(
                ocr_version=config.models.ocr.ocr_version,
                use_angle_cls=self.use_angle_cls,
                lang=self.lang,
                use_gpu=(self.device.upper() == 'GPU'),
                det_model_dir=det_model_dir,
                rec_model_dir=rec_model_dir,
                cls_model_dir=cls_model_dir,
                show_log=False,
                rec_image_shape='3,48,320',
                det_db_thresh=0.25,
                det_db_box_thresh=0.45,
                det_db_unclip_ratio=1.6,
                drop_score=0.4,
                det_limit_side_len=1280,
            )

            PaddleOCRProcessor._config = model_config_key
            logger.info("Model loaded")

        self.ocr_model = PaddleOCRProcessor._model

    def ocr(self, file_path: str) -> List[List]:
        return self.ocr_model.ocr(file_path, cls=self.use_angle_cls)

    def extract_text(self, file_path: str) -> str:
        result = self.ocr(file_path)

        if not result or not result[0]:
            return ""
        lines = []
        for page in result:
            if page:
                for line in page:
                    if line and len(line) > 1:
                        text = line[1][0] if isinstance(line[1], (list, tuple)) else str(line[1])
                        lines.append(text)
        
        return "\n".join(lines)
