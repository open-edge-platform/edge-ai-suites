# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import logging
import os
from pathlib import Path
from typing import List, Union

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

OPENAI_CLIP_MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
OPENAI_CLIP_STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
IMAGE_SIZE = 224
MAX_SEQ_LEN = 77
ONNX_OPSET_VERSION = 18


class CLIPHandler:
    """OpenVINO-based CLIP handler for xlm-roberta-base-ViT-B-32.

    Loads pre-exported OpenVINO IR models for text and image encoders.
    No torch or open_clip dependency at runtime.
    """

    def __init__(self, model_config: dict):
        self.model_config = model_config
        self.device = model_config.get("device", "CPU")
        self._visual_model = None
        self._text_model = None
        self._tokenizer = None

    def load_model(self) -> None:
        import openvino as ov
        from transformers import AutoTokenizer

        model_dir = Path(os.getcwd()).parent / "models" / "openvino" / "clip"

        visual_path = model_dir / "visual.xml"
        text_path = model_dir / "text.xml"

        if not visual_path.exists() or not text_path.exists():
            logger.info(f"OpenVINO IR not found at {model_dir}, running export...")
            self._export_to_openvino(model_dir)

        core = ov.Core()
        self._visual_model = core.compile_model(str(visual_path), self.device)
        self._text_model = core.compile_model(str(text_path), self.device)

        tokenizer_dir = model_dir / "tokenizer"
        if tokenizer_dir.exists():
            self._tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_dir))
        else:
            self._tokenizer = AutoTokenizer.from_pretrained("xlm-roberta-base")
            tokenizer_dir.mkdir(parents=True, exist_ok=True)
            self._tokenizer.save_pretrained(str(tokenizer_dir))

        logger.info(f"CLIP OpenVINO models loaded from {model_dir} (device={self.device})")

    def _export_to_openvino(self, model_dir: Path) -> None:
        """One-time export: open_clip → ONNX → OpenVINO IR + tokenizer."""
        import torch
        import open_clip
        from transformers import AutoTokenizer

        model_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Loading open_clip model for export...")
        model, _, _ = open_clip.create_model_and_transforms(
            "xlm-roberta-base-ViT-B-32", pretrained="laion5b_s13b_b90k"
        )
        model.eval()

        # Export visual encoder
        dummy_image = torch.randn(1, 3, IMAGE_SIZE, IMAGE_SIZE)
        onnx_visual = str(model_dir / "visual.onnx")
        torch.onnx.export(
            model.visual, dummy_image, onnx_visual,
            input_names=["image"],
            output_names=["image_features"],
            dynamic_shapes=({0: torch.export.Dim("batch")},),
            opset_version=ONNX_OPSET_VERSION,
            dynamo=True,
        )

        # Export text encoder
        dummy_text = torch.randint(0, 250002, (1, MAX_SEQ_LEN), dtype=torch.long)
        onnx_text = str(model_dir / "text.onnx")
        torch.onnx.export(
            model.text, dummy_text, onnx_text,
            input_names=["input_ids"],
            output_names=["text_features"],
            dynamic_shapes=({0: torch.export.Dim("batch"), 1: torch.export.Dim("seq_len")},),
            opset_version=ONNX_OPSET_VERSION,
            dynamo=True,
        )

        # Convert ONNX to OpenVINO IR.
        # openvino's convert_model probes the PyTorch frontend first, which calls
        # torch.export.load() on the .onnx file and logs a noisy (harmless) failure
        # before falling back to the ONNX frontend. Silence just that probe.
        torch_export_log = logging.getLogger("torch.export")
        prev_level = torch_export_log.level
        torch_export_log.setLevel(logging.ERROR)
        try:
            import openvino as ov
            ov_visual = ov.convert_model(onnx_visual)
            ov.save_model(ov_visual, str(model_dir / "visual.xml"), compress_to_fp16=True)

            ov_text = ov.convert_model(onnx_text)
            ov.save_model(ov_text, str(model_dir / "text.xml"), compress_to_fp16=True)
        finally:
            torch_export_log.setLevel(prev_level)

        # Clean up ONNX intermediates
        for onnx_file in (onnx_visual, onnx_text):
            for stale in model_dir.glob(Path(onnx_file).name + "*"):
                stale.unlink(missing_ok=True)

        # Save tokenizer locally
        tokenizer = AutoTokenizer.from_pretrained("xlm-roberta-base")
        tokenizer.save_pretrained(str(model_dir / "tokenizer"))

        # Free export-only memory
        del model, ov_visual, ov_text
        logger.info(f"Export complete → {model_dir}")

    def _preprocess_image(self, image: Image.Image) -> np.ndarray:
        """Resize, center-crop, normalize a PIL image to (1, 3, 224, 224) float32."""
        # Resize shortest edge to IMAGE_SIZE with bicubic
        w, h = image.size
        if w < h:
            new_w = IMAGE_SIZE
            new_h = int(h * IMAGE_SIZE / w)
        else:
            new_h = IMAGE_SIZE
            new_w = int(w * IMAGE_SIZE / h)
        image = image.resize((new_w, new_h), Image.BICUBIC)

        # Center crop
        left = (new_w - IMAGE_SIZE) // 2
        top = (new_h - IMAGE_SIZE) // 2
        image = image.crop((left, top, left + IMAGE_SIZE, top + IMAGE_SIZE))

        # To float32 [0, 1], then normalize
        arr = np.array(image, dtype=np.float32) / 255.0
        arr = (arr - OPENAI_CLIP_MEAN) / OPENAI_CLIP_STD

        # HWC → CHW, add batch dim
        arr = arr.transpose(2, 0, 1)[np.newaxis, ...]
        return arr

    def _l2_normalize(self, x: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(x, axis=-1, keepdims=True)
        norm = np.maximum(norm, 1e-8)
        return x / norm

    def encode_text(self, texts: Union[str, List[str]]) -> np.ndarray:
        if isinstance(texts, str):
            texts = [texts]

        tokens = self._tokenizer(
            texts, padding="max_length", truncation=True,
            max_length=MAX_SEQ_LEN, return_tensors="np",
        )
        input_ids = tokens["input_ids"].astype(np.int64)

        result = self._text_model(input_ids)
        features = result[self._text_model.output(0)]
        return self._l2_normalize(features.astype(np.float32))

    def encode_image(self, images: Union[Image.Image, List[Image.Image]]) -> np.ndarray:
        if isinstance(images, Image.Image):
            images = [images]

        batch = np.concatenate(
            [self._preprocess_image(img.convert("RGB")) for img in images], axis=0
        )

        result = self._visual_model(batch)
        features = result[self._visual_model.output(0)]
        return self._l2_normalize(features.astype(np.float32))

    def get_embedding_dim(self) -> int:
        return 512
