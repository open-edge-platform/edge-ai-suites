# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Sensor-vector classification via an OpenVINO MLP model.

Ported from ``SensorFlatHandler`` in intel/predictive-maintenance-pipeline
(src/inference/handlers/sensor_flat.py), trimmed to the flat-CSV / MLP
sensor path only — model loading, feature normalization, and per-sample
inference. Late fusion with other modalities lives in ``fusion.py`` and is
intentionally decoupled from this module so a sensor-only classification
use case does not need to pull in image-classifier or fusion code.
"""

import csv
import json
from pathlib import Path
from typing import Optional


class SensorMLPClassifier:
    """Runs a flat-vector MLP classifier over CSV sensor readings.

    Expects a CSV with one row per sample, a configurable set of numeric
    feature columns, and a join key column used to match rows to external
    sample identifiers (e.g. an image filename stem for a paired image
    modality, or any other per-sample id).
    """

    def __init__(
        self,
        model_path: str,
        data_path: str,
        feature_columns: list[str],
        join_column: str,
        device: str = "CPU",
    ):
        self.model_path = model_path
        self.data_path = data_path
        self.feature_columns = feature_columns
        self.join_column = join_column
        self.device = device

        self._compiled = None
        self._output_layer = None
        self._lookup: dict[str, list[float]] = {}
        self._readings_lookup: dict[str, dict] = {}
        self._mean = None
        self._std = None

    def load(self) -> None:
        """Load sensor CSV rows and compute normalization stats."""
        import numpy as np

        self._lookup = {}
        self._readings_lookup = {}
        all_vals = []
        with open(self.data_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = row[self.join_column]
                vals = [float(row[col]) for col in self.feature_columns]
                self._lookup[key] = vals
                self._readings_lookup[key] = {
                    "sensor_raw_json": json.dumps(
                        {col: vals[idx] for idx, col in enumerate(self.feature_columns)}
                    )
                }
                all_vals.append(vals)

        all_vals = np.array(all_vals, dtype=np.float32)
        self._mean = all_vals.mean(axis=0)
        self._std = all_vals.std(axis=0)
        self._std[self._std == 0] = 1.0

    def _ensure_model_loaded(self) -> None:
        if self._compiled is not None:
            return
        import openvino as ov

        core = ov.Core()
        model = core.read_model(self.model_path)
        # Inference is always batch-1, but the exported model declares a dynamic
        # batch dimension. NPU requires static shapes, so pin the input to
        # [1, n_features] before compiling (a no-op for CPU/GPU).
        try:
            model.reshape([1, len(self.feature_columns)])
        except Exception:
            pass
        self._compiled = core.compile_model(model, self.device)
        self._output_layer = self._compiled.output(0)

    def infer(self, sample_keys: list[str], n_classes: int) -> list[dict]:
        """Run inference for each sample key (join-column value), in order.

        Samples with no matching CSV row fall back to a uniform probability
        distribution rather than failing the whole batch.
        """
        import numpy as np

        self._ensure_model_loaded()
        uniform = [1.0 / n_classes] * n_classes
        results = []

        for key in sample_keys:
            if key not in self._lookup:
                results.append({"source": key, "probabilities": uniform})
                continue

            sensor_vals = self._lookup[key]
            input_data = np.array([sensor_vals], dtype=np.float32)
            input_data = (input_data - self._mean) / self._std
            output = self._compiled([input_data])[self._output_layer]

            probs = output[0]
            if probs.min() < 0 or probs.sum() < 0.99 or probs.sum() > 1.01:
                exp_probs = np.exp(probs - np.max(probs))
                probs = exp_probs / exp_probs.sum()

            result = {"source": key, "probabilities": probs.tolist()}
            result.update(self._readings_lookup[key])
            results.append(result)

        return results

    @staticmethod
    def sample_key_from_image_name(image_name: str) -> str:
        """Derive the join key from an image filename (strip extension)."""
        return Path(image_name).stem
