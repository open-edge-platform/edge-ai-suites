import os
import shutil
import logging
from pathlib import Path
from typing import Optional
from utils.config_loader import config

logger = logging.getLogger(__name__)

# Paths
PADDLE_HOME = Path.home() / ".paddleocr" / "whl"


def get_models_ocr_paddle() -> Path:
    return Path(config.models.ocr.model_dir)


class PaddleOCRModelManager:
    
    @staticmethod
    def _ensure_models_dir() -> Path:
        models_dir = get_models_ocr_paddle()
        models_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Models directory ensured: {models_dir.resolve()}")
        return models_dir
    
    @staticmethod
    def _move_paddle_models() -> bool:
        models_dir = get_models_ocr_paddle() 
        if not PADDLE_HOME.exists():
            logger.warning(f"PaddleOCR home not found: {PADDLE_HOME}")
            return False
        PaddleOCRModelManager._ensure_models_dir()
        try:
            logger.info(f"Moving PaddleOCR models from {PADDLE_HOME} to {models_dir}...")
            source_dirs = [
                item for item in PADDLE_HOME.iterdir()
                if item.is_dir() and any(item.iterdir())
            ]
            if not source_dirs:
                logger.info("No non-empty model directories found under PaddleOCR whl cache")
                return bool(list(models_dir.glob("*")))

            moved_count = 0
            skipped_existing = 0

            for item in source_dirs:
                dest = models_dir / item.name
                if dest.exists():
                    logger.debug(f"Skipping existing: {dest.name}")
                    skipped_existing += 1
                    continue
                logger.debug(f"Moving: {item.name} -> {dest.name}")
                shutil.move(str(item), str(dest))
                moved_count += 1

            logger.info(
                f"PaddleOCR model move completed: moved={moved_count}, skipped_existing={skipped_existing}"
            )
            return moved_count > 0 or skipped_existing > 0
            
        except Exception as e:
            logger.error(f"Failed to move PaddleOCR models: {e}")
            return False
    
    @staticmethod
    def initialize(
        lang: str,
        use_angle_cls: bool,
        device: str
    ) -> Optional[object]:
        try:
            logger.info(f"Initializing PaddleOCR: lang={lang}, device={device}")
            from paddleocr import PaddleOCR  
            
            paddle_ocr = PaddleOCR(
                ocr_version=config.models.ocr.ocr_version,
                use_angle_cls=use_angle_cls,
                lang=lang,
                use_gpu=(device.upper() == 'GPU'),
                det_model_name=config.models.ocr.det_model,
                rec_model_name=config.models.ocr.rec_model,
                cls_model_=(config.models.ocr.cls_model if use_angle_cls else None),
                show_log=False,
                rec_image_shape='3,48,320',
                det_db_thresh=0.25,
                det_db_box_thresh=0.45,
                det_db_unclip_ratio=1.6,
                drop_score=0.4,
                det_limit_side_len=1280,
            )
            PaddleOCRModelManager._ensure_models_dir()
            PaddleOCRModelManager._move_paddle_models()
            logger.info(f"PaddleOCR initialized successfully")
            return paddle_ocr
            
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {e}", exc_info=True)
            raise
