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
        lang: str,
        use_angle_cls: bool,
        device: str,
        ir_models_dir: str,
        det_db_thresh: float = 0.2,
        det_db_box_thresh: float = 0.45,
        det_db_unclip_ratio: float = 1.4,
        drop_score: float = 0.5,
        max_candidates: int = 3000,
        rec_image_shape: str = '3,48,320',
        **kwargs
    ):
        super().__init__(lang, use_angle_cls, device)
        self.ir_models_dir = Path(ir_models_dir)
        self.lang = lang

        self.det_db_thresh = det_db_thresh
        self.det_db_box_thresh = det_db_box_thresh
        self.det_db_unclip_ratio = det_db_unclip_ratio
        self.max_candidates = max_candidates

        self.drop_score = drop_score
        rec_shape = [int(x) for x in rec_image_shape.replace(' ', '').split(',')]
        self.rec_image_height = rec_shape[1]
        self.rec_image_width = rec_shape[2]

        self._load_char_dict()
        self._load_models()

    def _load_char_dict(self):
        import yaml

        yml_path = self.ir_models_dir / "rec" / config.models.ocr.rec_model / "inference.yml"
        if yml_path.exists():
            with open(yml_path, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f)
            char_list = cfg.get('PostProcess', {}).get('character_dict', [])
            self.char_dict = ['blank'] + char_list + [' ']
            logger.info(f"Loaded character dictionary from inference.yml: {len(self.char_dict)} chars")
            return

        raise FileNotFoundError(
            f"Character dictionary not found at {yml_path}. "
            "Ensure OCR models have been downloaded and converted."
        )

    def _load_models(self):
        import openvino as ov
        config_key = (str(self.ir_models_dir), self.device)
        if OpenVINOOCRProcessor._config == config_key and OpenVINOOCRProcessor._det_compiled:
            self.det_compiled = OpenVINOOCRProcessor._det_compiled
            self.rec_compiled = OpenVINOOCRProcessor._rec_compiled
            self.cls_compiled = OpenVINOOCRProcessor._cls_compiled
            self.char_dict = OpenVINOOCRProcessor._char_dict
            return

        logger.info("Loading OpenVINO models...")
        core = ov.Core()

        det_ir = self.ir_models_dir / "det" / config.models.ocr.det_model / "inference.xml"
        if not det_ir.exists():
            raise FileNotFoundError(f"Detection model not found: {det_ir}")
        logger.info(f"Loading detection: {det_ir}")
        self.det_compiled = core.compile_model(str(det_ir), self.device)
        OpenVINOOCRProcessor._det_compiled = self.det_compiled

        rec_ir = self.ir_models_dir / "rec" / config.models.ocr.rec_model / "inference.xml"
        if not rec_ir.exists():
            raise FileNotFoundError(f"Recognition model not found: {rec_ir}")
        logger.info(f"Loading recognition: {rec_ir}")
        rec_model = core.read_model(str(rec_ir))
        for input_layer in rec_model.inputs:
            input_shape = input_layer.partial_shape
            if input_shape.rank.is_static and input_shape.rank.get_length() == 4:
                input_shape[3] = -1
                rec_model.reshape({input_layer: input_shape})
        self.rec_compiled = core.compile_model(rec_model, self.device)
        OpenVINOOCRProcessor._rec_compiled = self.rec_compiled

        if self.use_angle_cls:
            cls_ir = self.ir_models_dir / "cls" / config.models.ocr.cls_model / "inference.xml"
            if cls_ir.exists():
                logger.info(f"Loading classification: {cls_ir}")
                self.cls_compiled = core.compile_model(str(cls_ir), self.device)
                OpenVINOOCRProcessor._cls_compiled = self.cls_compiled
            else:
                logger.warning(f"Classification model not found: {cls_ir}")
                self.cls_compiled = None
        else:
            self.cls_compiled = None

        OpenVINOOCRProcessor._config = config_key
        OpenVINOOCRProcessor._char_dict = self.char_dict
        logger.info("OpenVINO models loaded")

    def _detect(self, img: np.ndarray) -> List[np.ndarray]:
        ori_h, ori_w = img.shape[:2]
        img_input = pipeline.preprocess_det(img)
        output = self.det_compiled([img_input])[0]
        pred = output[0, 0]
        segmentation = pred > self.det_db_thresh
        boxes, scores = pipeline.boxes_from_bitmap(
            pred, segmentation, ori_w, ori_h,
            box_thresh=self.det_db_box_thresh,
            unclip_ratio=self.det_db_unclip_ratio,
            max_candidates=self.max_candidates
        )
        boxes = pipeline.filter_boxes(boxes, img.shape)
        boxes = pipeline.sorted_boxes(boxes)
        logger.debug(f"Detected {len(boxes)} text regions")
        return boxes

    def _recognize(self, img: np.ndarray, boxes: List[np.ndarray]) -> List[Tuple]:
        if not boxes:
            return []
        img_crop_list, valid_indices = pipeline.prep_for_recognition(boxes, img)

        if not img_crop_list:
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
