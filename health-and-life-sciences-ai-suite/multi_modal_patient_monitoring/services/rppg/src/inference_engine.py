"""Inference Engine - OpenVINO runtime for MTTS-CAN IR on Intel iGPU.

This engine consumes the OpenVINO IR model (XML+BIN) produced by the
patient-monitoring-assets container from the original Keras HDF5.
"""

import os
from pathlib import Path
import logging
from typing import Dict, Any

import numpy as np
import openvino as ov


logger = logging.getLogger(__name__)


class InferenceEngine:
    """MTTS-CAN inference engine using OpenVINO IR."""

    def __init__(self, model_path: str = "/models/rppg/mtts_can.xml"):
        """Initialize inference engine.

        The model is expected to be an OpenVINO IR (XML) file. Device
        selection is controlled via the RPPG_DEVICE environment variable,
        defaulting to "GPU" for Intel iGPU.
        """

        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"OpenVINO IR model not found: {self.model_path}")

        self.core = ov.Core()

        # Normalize device string so values like "GPU" or 'GPU' work
        raw_device = os.getenv("RPPG_DEVICE", "GPU")
        device = raw_device.strip().strip('"').strip("'")
        logger.info(f"Compiling OpenVINO model on device: {device}")

        self.compiled_model = self.core.compile_model(str(self.model_path), device)

        # Cache input/output ports for faster access
        self.inputs = list(self.compiled_model.inputs)
        self.output = self.compiled_model.output(0)

        logger.info("✓ OpenVINO model loaded successfully")
        for idx, inp in enumerate(self.inputs):
            pshape = inp.get_partial_shape()
            logger.info(f"  Input[{idx}] name={inp.get_any_name()} shape={pshape}")
        logger.info(f"  Output shape={self.output.get_partial_shape()}")

    def infer(self, diff_frames: np.ndarray, app_frames: np.ndarray) -> np.ndarray:
        """Run inference on preprocessed frames.

        The model expects two inputs: [appearance, motion]. The preprocessor
        already prepares `app_frames` and `diff_frames` with the correct
        shapes, so we pass them through as-is.
        """

        if diff_frames.shape != app_frames.shape:
            raise ValueError(f"Shape mismatch: {diff_frames.shape} vs {app_frames.shape}")

        # Map inputs by index to avoid relying on specific names
        input_data: Dict[int, Any] = {
            0: app_frames,
            1: diff_frames,
        }

        results = self.compiled_model(input_data)
        predictions = results[self.output]
        return predictions

    def get_model_info(self) -> dict:
        """Get model metadata (input/output shapes, etc.)."""

        def _shape_from_partial(pshape):
            dims = []
            for d in pshape:
                if d.is_static:
                    dims.append(int(d))
                else:
                    dims.append(-1)
            return dims

        input_shapes = [_shape_from_partial(inp.get_partial_shape()) for inp in self.inputs]
        output_shape = _shape_from_partial(self.output.get_partial_shape())

        return {
            "inputs": len(self.inputs),
            "outputs": 1,
            "input_shapes": input_shapes,
            "output_shapes": [output_shape],
        }
