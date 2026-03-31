# Derived from: edge-ai-libraries/microservices/multimodal-embedding-serving/src/
# Original package: multimodal-embedding-serving v0.1.1
# Only CLIP-related functionality retained; OpenVINO export removed.

from .registry import get_model_handler
from .wrapper import EmbeddingModel
from .clip_handler import CLIPHandler

__all__ = ["get_model_handler", "EmbeddingModel", "CLIPHandler"]
