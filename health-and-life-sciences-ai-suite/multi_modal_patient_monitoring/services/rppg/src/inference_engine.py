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

    def __init__(self, model_path: str = "/models/rppg/mtts_can.xml", batch_size: int = 10):
        """Initialize inference engine.

        The model is expected to be an OpenVINO IR (XML) file. Device
        selection is controlled via the RPPG_DEVICE environment variable,
        defaulting to "GPU" for Intel iGPU.

        For NPU, we also make sure that any dynamic batch dimension is
        reshaped to a concrete value to satisfy the compiler/runtime.
        """

        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"OpenVINO IR model not found: {self.model_path}")

        # Use provided batch size (from config) or env override
        try:
            self.batch_size = int(os.getenv("RPPG_BATCH_SIZE", str(batch_size)))
        except ValueError:
            logger.warning("Invalid RPPG_BATCH_SIZE env var; falling back to batch_size=%d", batch_size)
            self.batch_size = batch_size

        self.core = ov.Core()

        # Normalize device string so values like "GPU" or 'GPU' work
        raw_device = os.getenv("RPPG_DEVICE", "GPU")
        device = raw_device.strip().strip('"').strip("'")
        logger.info(f"Compiling OpenVINO model on device: {device}")

        self.compiled_model = None
        selected_device = device

        try:
            # For NPU we explicitly read the model and fix dynamic shapes
            if device.upper() == "NPU":
                ov_model = self.core.read_model(str(self.model_path))
                self._fix_dynamic_shapes_for_npu(ov_model)
                self.compiled_model = self.core.compile_model(ov_model, device)
            else:
                self.compiled_model = self.core.compile_model(str(self.model_path), device)
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to compile OpenVINO model on device %s: %s", device, e, exc_info=True)
            # Fallback device can be overridden via env, default to CPU which is always available
            fallback_device = os.getenv("RPPG_FALLBACK_DEVICE", "CPU")
            if fallback_device and fallback_device != device:
                logger.info("Falling back to device: %s", fallback_device)
                self.compiled_model = self.core.compile_model(str(self.model_path), fallback_device)
                selected_device = fallback_device
            else:
                raise

        # Cache input/output ports for faster access
        self.inputs = list(self.compiled_model.inputs)
        self.output = self.compiled_model.output(0)

        logger.info("✓ OpenVINO model loaded successfully on device: %s", selected_device)
        for idx, inp in enumerate(self.inputs):
            pshape = inp.get_partial_shape()
            logger.info("  Input[%d] name=%s shape=%s", idx, inp.get_any_name(), pshape)
        logger.info("  Output shape=%s", self.output.get_partial_shape())

    def _fix_dynamic_shapes_for_npu(self, model) -> None:
        """Ensure dynamic dimensions (especially batch) have concrete bounds for NPU.

        The NPU compiler requires upper bounds for all dimensions. We set the
        batch dimension to the configured batch size and clamp any other
        remaining dynamic dims to 1 as a conservative upper bound.
        """

        for inp in model.inputs:
            pshape = inp.get_partial_shape()
            # Check if we actually have any dynamic dims; if not, skip
            has_dynamic = any(not dim.is_static for dim in pshape)
            if not has_dynamic:
                continue

            new_dims = []
            for idx, dim in enumerate(pshape):
                if dim.is_static:
                    # Safe conversion of static Dimension to int via get_length()
                    new_dims.append(dim.get_length())
                else:
                    if idx == 0:
                        # Dynamic batch -> set to configured batch size
                        new_dims.append(self.batch_size)
                    else:
                        # Other dynamic dims are unusual for this model; set to 1
                        logger.warning(
                            "Dynamic non-batch dimension at index %d for input %s; setting to 1",
                            idx,
                            inp.get_any_name(),
                        )
                        new_dims.append(1)

            new_shape = ov.PartialShape(new_dims)
            logger.info(
                "Reshaping input %s from %s to %s for NPU",
                inp.get_any_name(),
                pshape,
                new_shape,
            )
            # Map directly from input port to new partial shape
            model.reshape({inp: new_shape})

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
                    # Use get_length() instead of int(d) for robustness
                    dims.append(d.get_length())
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
