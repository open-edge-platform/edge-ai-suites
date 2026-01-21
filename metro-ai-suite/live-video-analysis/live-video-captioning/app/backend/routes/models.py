# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from fastapi import APIRouter
from ..config import MODELS_DIR, DETECTION_MODELS_DIR
from ..models import ModelList
from ..services import discover_models, discover_detection_models

router = APIRouter(prefix="/api", tags=["models"])


@router.get("/vlm-models", response_model=ModelList)
async def list_models() -> ModelList:
    """List available VLM models from the models directory."""
    models = discover_models(MODELS_DIR)
    return ModelList(models=models)


@router.get("/detection-models", response_model=ModelList)
async def list_detection_models() -> ModelList:
    """List available detection models from the detection models directory."""
    models = discover_detection_models(DETECTION_MODELS_DIR)
    return ModelList(models=models)