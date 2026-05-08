from components.ocr.base_ocr import BaseOCR
from components.ocr.openvino import openvino_pipeline as pipeline
from utils.config_loader import config
from typing import List, Tuple, Optional
import logging
import numpy as np
import cv2
from pathlib import Path

logger = logging.getLogger(__name__)


class OpenVINOOCRProcessor(BaseOCR):    
    _det_compiled = None
    _rec_compiled = None
    _cls_compiled = None
    _config = None
    _char_dict = None

    def __init__(
        self,
        lang: str ,
        use_angle_cls: bool ,
        device: str,
        ir_models_dir: str,
        det_db_thresh: float = 0.25,
        det_db_box_thresh: float = 0.45,
        det_db_unclip_ratio: float = 1.6,
        drop_score: float = 0.4,
        det_limit_side_len: int = 1280,
        rec_image_shape: str = '3,48,320',
        **kwargs
    ):
        super().__init__(lang, use_angle_cls, device)
        self.ir_models_dir = Path(ir_models_dir)
        self.lang = lang
        
        self.det_db_thresh = det_db_thresh
        self.det_db_box_thresh = det_db_box_thresh
        self.det_db_unclip_ratio = det_db_unclip_ratio
        self.det_limit_side_len = det_limit_side_len
        
        self.drop_score = drop_score
        rec_shape = [int(x) for x in rec_image_shape.replace(' ', '').split(',')]
        self.rec_image_height = rec_shape[1]  
        self.rec_image_width = rec_shape[2]   
        
        self._load_char_dict()
        self._load_models()

    def _load_char_dict(self):
        import os
        cache_file = os.path.join(config.models.ocr.model_dir, 
                                  f'ppocrv4_{self.lang}_chars.txt')
        
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                self.char_dict = [line.rstrip('\n\r') for line in f]
            logger.info(f"Loaded cached dictionary: {len(self.char_dict)} chars from {cache_file}")
            return
        
        from paddleocr import PaddleOCR
        logger.info("Extracting character dictionary from PaddleOCR...")
        
        models_ocr_paddle = Path(config.models.ocr.model_dir)
        det_model = config.models.ocr.det_model
        rec_model = config.models.ocr.rec_model
        
        det_dir = models_ocr_paddle / "det" / self.lang / det_model
        rec_dir = models_ocr_paddle / "rec" / self.lang / rec_model
        
        ocr_kwargs = {'use_angle_cls': True, 'lang': self.lang, 'show_log': False}
        
        if det_dir.exists():
            ocr_kwargs['det_model_dir'] = str(det_dir)
        if rec_dir.exists():
            ocr_kwargs['rec_model_dir'] = str(rec_dir)
        
        ocr = PaddleOCR(**ocr_kwargs)
        
        self.char_dict = list(ocr.text_recognizer.postprocess_op.character)
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            for c in self.char_dict:
                f.write(c + '\n')
        
        logger.info(f"Loaded dictionary with {len(self.char_dict)} characters")

    def _load_models(self):
        import openvino as ov
        config_key = (str(self.ir_models_dir), self.device)
        if OpenVINOOCRProcessor._config == config_key and OpenVINOOCRProcessor._det_compiled:
            self.det_compiled = OpenVINOOCRProcessor._det_compiled
            self.rec_compiled = OpenVINOOCRProcessor._rec_compiled
            self.cls_compiled = OpenVINOOCRProcessor._cls_compiled
            return
        
        logger.info("Loading OpenVINO models...")
        core = ov.Core()
        
        det_path = self._find_model("det")
        if det_path:
            logger.info(f"Loading detection: {det_path}")
            self.det_compiled = core.compile_model(core.read_model(str(det_path)), self.device)
            OpenVINOOCRProcessor._det_compiled = self.det_compiled
        else:
            raise FileNotFoundError(f"Detection model not found in {self.ir_models_dir}")
        
        rec_path = self._find_model("rec")
        if rec_path:
            logger.info(f"Loading recognition: {rec_path}")
            rec_model = core.read_model(str(rec_path))
            
            for input_layer in rec_model.inputs:
                input_shape = input_layer.partial_shape
                input_shape[3] = -1  
                rec_model.reshape({input_layer: input_shape})
            
            self.rec_compiled = core.compile_model(rec_model, self.device)
            OpenVINOOCRProcessor._rec_compiled = self.rec_compiled
        else:
            raise FileNotFoundError(f"Recognition model not found in {self.ir_models_dir}")
        
        cls_path = self._find_model("cls")
        if cls_path and self.use_angle_cls:
            logger.info(f"Loading classification: {cls_path}")
            self.cls_compiled = core.compile_model(core.read_model(str(cls_path)), self.device)
            OpenVINOOCRProcessor._cls_compiled = self.cls_compiled
        else:
            self.cls_compiled = None
        
        OpenVINOOCRProcessor._config = config_key
        logger.info("OpenVINO models loaded")

    def _find_model(self, model_type: str) -> Optional[Path]:
        lang = getattr(config.models.ocr, 'lang', 'en')
        det_model = config.models.ocr.det_model
        rec_model = config.models.ocr.rec_model
        cls_model = config.models.ocr.cls_model
        
        patterns = {
            "det": [f"det/{lang}/{det_model}/*.xml", f"det/{lang}/*det*/*.xml", "*det*/*.xml"],
            "rec": [f"rec/{lang}/{rec_model}/*.xml", f"rec/{lang}/*rec*/*.xml", "*rec*/*.xml"],
            "cls": [f"cls/{cls_model}/*.xml", f"cls/*cls*/*.xml", "*cls*/*.xml"],
        }
        
        for pattern in patterns.get(model_type, []):
            matches = list(self.ir_models_dir.glob(pattern))
            if matches:
                logger.info(f"Found {model_type} model: {matches[0]}")
                return matches[0]
        
        logger.warning(f"Model not found for {model_type} in {self.ir_models_dir}")
        return None

    def _detect(self, img: np.ndarray) -> List[np.ndarray]:
        ori_h, ori_w = img.shape[:2]
        det_size = 640  
        img_input = pipeline.preprocess_det(img, det_size)
        output = self.det_compiled([img_input])[0]
        pred = output[0, 0] 
        segmentation = pred > self.det_db_thresh
        boxes, scores = pipeline.boxes_from_bitmap(
            pred, segmentation, ori_w, ori_h,
            box_thresh=self.det_db_box_thresh,
            unclip_ratio=self.det_db_unclip_ratio
        )
        boxes = pipeline.filter_boxes(boxes, img.shape)
        boxes = pipeline.sorted_boxes(boxes)
        logger.debug(f"Detected {len(boxes)} text regions")
        return boxes

    def _recognize(self, img: np.ndarray, boxes: List[np.ndarray]) -> List[Tuple]:
        if not boxes:
            logger.warning("Recognition: No boxes to process")
            return []
        img_crop_list, valid_indices = pipeline.prep_for_recognition(boxes, img)
        
        if not img_crop_list:
            logger.warning("Recognition: No valid crops after preprocessing")
            return []
        
        img_num = len(img_crop_list)
        logger.info(f"Recognition: Processing {img_num} text crops")
        
        width_list = [crop.shape[1] / float(crop.shape[0]) for crop in img_crop_list]
        indices = np.argsort(np.array(width_list))
        
        batch_num = 6  
        rec_res = [['', 0.0]] * img_num
        
        for beg_img_no in range(0, img_num, batch_num):
            norm_img_batch = pipeline.batch_text_boxes(
                img_crop_list, indices, beg_img_no, batch_num,
                self.rec_image_height, self.rec_image_width
            )
            rec_results = self.rec_compiled([norm_img_batch])[0]
            num_classes = rec_results.shape[-1]
            if num_classes != len(self.char_dict):
                logger.error(f"MISMATCH! Model outputs {num_classes} classes but char_dict has {len(self.char_dict)}")

            decoded = pipeline.ctc_decode_batch(rec_results, self.char_dict)
            
            end_img_no = min(img_num, beg_img_no + batch_num)
            for rno in range(len(decoded)):
                rec_res[indices[beg_img_no + rno]] = decoded[rno]
        
        results = []
        for i, (text, conf) in enumerate(rec_res):
            original_idx = valid_indices[i]
            if text.strip() and conf > self.drop_score:
                results.append((boxes[original_idx], (text, conf)))
        
        logger.info(f"Recognized {len(results)} text regions (drop_score={self.drop_score})")
        return results
    
    def ocr(self, file_path) -> List[List]:
        if isinstance(file_path, str):
            img = cv2.imread(file_path)
        elif isinstance(file_path, np.ndarray):
            img = file_path.copy()
        else:
            img = np.array(file_path)
        
        if img is None:
            return [[]]
        
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        
        boxes = self._detect(img)
        if len(boxes) == 0:
            return [[]]
        results = self._recognize(img, boxes)
        
        if results:
            results.sort(key=lambda x: x[0][0][1])
        return [results]

    def extract_text(self, file_path) -> str:
        result = self.ocr(file_path)
        if not result or not result[0]:
            return ""
        lines = [item[1][0] for item in result[0]]
        return "\n".join(lines)
