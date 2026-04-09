# Derived from: edge-ai-libraries/microservices/multimodal-embedding-serving/src/models/base.py
# Original package: multimodal-embedding-serving v0.1.1
# Only CLIP-related functionality retained; OpenVINO export removed.
#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from abc import ABC, abstractmethod
from typing import List, Union, Dict, Any
from PIL import Image
import numpy as np
import torch


class BaseEmbeddingModel(ABC):
    """Abstract base class for multimodal embedding models."""

    def __init__(self, model_config: Dict[str, Any]):
        self.model_config = model_config
        self.model = None
        self.tokenizer = None
        self.preprocess = None
        self.device = model_config.get("device", "cpu")
        default_modalities = {"text", "image"}
        config_modalities = model_config.get("modalities")
        if config_modalities:
            self.supported_modalities = set(config_modalities)
        else:
            self.supported_modalities = default_modalities

    @abstractmethod
    def load_model(self) -> None:
        pass

    @abstractmethod
    def encode_text(self, texts: Union[str, List[str]]) -> torch.Tensor:
        pass

    @abstractmethod
    def encode_image(self, images: Union[Image.Image, List[Image.Image], torch.Tensor]) -> torch.Tensor:
        pass

    # ------------------------------------------------------------------
    # Optional capability hooks
    # ------------------------------------------------------------------

    def supports_text(self) -> bool:
        return "text" in self.supported_modalities

    def supports_image(self) -> bool:
        return "image" in self.supported_modalities

    def supports_video(self) -> bool:
        return "video" in self.supported_modalities or self.supports_image()

    def prepare_query(self, text: str) -> str:
        return text

    def prepare_documents(self, texts: List[str]) -> List[str]:
        return texts

    def get_embedding_dim(self) -> int:
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        return 512  # Default; subclasses should override
