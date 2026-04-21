# Derived from: edge-ai-libraries/microservices/multimodal-embedding-serving/src/models/handlers/clip_handler.py
# Original package: multimodal-embedding-serving v0.1.1
# Only CLIP-related functionality retained; OpenVINO export removed.
#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import logging
import os
from pathlib import Path
from typing import List, Union, Dict, Any, Optional

import torch
import torch.nn.functional as F
from PIL import Image
import open_clip

from .base import BaseEmbeddingModel

logger = logging.getLogger(__name__)


class CLIPHandler(BaseEmbeddingModel):
    """Handler for CLIP models using the open_clip library (PyTorch only)."""

    def __init__(self, model_config: Dict[str, Any]):
        super().__init__(model_config)
        self.model_name = model_config["model_name"]
        self.pretrained = model_config["pretrained"]
        self.device = model_config.get("device", "CPU")
        self._embedding_dim: Optional[int] = None

    def load_model(self) -> None:
        try:
            self._embedding_dim = None

            local_path = Path(os.getcwd()).parent / "models" / "clip" / f"{self.model_name}-{self.pretrained}.pt"
            if local_path.exists():
                logger.info(f"Loading CLIP model {self.model_name} from local cache: {local_path}")
                self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                    self.model_name,
                    pretrained=str(local_path),
                )
            else:
                logger.info(f"Downloading CLIP model {self.model_name} with pretrained: {self.pretrained}")
                self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                    self.model_name,
                    pretrained=self.pretrained,
                )
                local_path.parent.mkdir(parents=True, exist_ok=True)
                torch.save(self.model.state_dict(), str(local_path))
                logger.info(f"Saved CLIP model weights to local cache: {local_path}")

            self.tokenizer = open_clip.get_tokenizer(self.model_name)
            self.model.eval()
            logger.info(f"CLIP model {self.model_name} loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load CLIP model {self.model_name}: {e}")
            raise

    def encode_text(self, texts: Union[str, List[str]]) -> torch.Tensor:
        if isinstance(texts, str):
            texts = [texts]

        tokenized = self.tokenizer(texts)

        with torch.no_grad():
            text_features = self.model.encode_text(tokenized)

        text_features = F.normalize(text_features, dim=-1)
        return text_features

    def encode_image(self, images: Union[Image.Image, List[Image.Image], torch.Tensor]) -> torch.Tensor:
        if isinstance(images, torch.Tensor):
            image_tensor = images
        elif isinstance(images, Image.Image):
            image_tensor = self.preprocess(images).unsqueeze(0)
        else:  # list of PIL Images
            image_tensor = torch.stack([self.preprocess(img) for img in images])

        with torch.no_grad():
            image_features = self.model.encode_image(image_tensor)

        image_features = F.normalize(image_features, dim=-1)
        return image_features

    def get_embedding_dim(self) -> int:
        if self._embedding_dim is not None:
            return self._embedding_dim

        if self.preprocess is None:
            raise RuntimeError("Preprocessing pipeline not initialized. Call load_model() first.")

        image_size = self._get_preprocess_image_size()
        dummy_image = Image.new("RGB", (image_size, image_size), color=0)
        image_tensor = self.preprocess(dummy_image).unsqueeze(0)

        if self.model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        try:
            sample_param = next(self.model.parameters())
            device = sample_param.device
            dtype = sample_param.dtype
        except StopIteration:
            device = torch.device("cpu")
            dtype = torch.float32

        image_tensor = image_tensor.to(device=device, dtype=dtype)
        with torch.no_grad():
            features = self.model.encode_image(image_tensor)
        self._embedding_dim = int(features.shape[-1])

        return self._embedding_dim

    def _get_preprocess_image_size(self) -> int:
        default_size = 224

        if self.preprocess is None:
            return default_size

        transforms = getattr(self.preprocess, "transforms", None)
        if not transforms:
            return default_size

        for transform in transforms:
            size = getattr(transform, "size", None)
            if size is None:
                continue
            if isinstance(size, (tuple, list)) and len(size) > 0:
                return int(size[0])
            if isinstance(size, int):
                return int(size)

        return default_size
