# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Whole-image classification via a direct OpenVINO inference call.

Ported from ``OpenVINOClassifyHandler`` in
intel/predictive-maintenance-pipeline (src/inference/handlers/openvino_classify.py).
Used for the "image" branch of a multimodal (image + sensor) classification
pipeline; this bypasses DL Streamer/gvaclassify since the reference model is
run directly through the OpenVINO runtime API against a folder of images.
"""

from pathlib import Path


class ImageClassifier:
    """Runs a single-label image classification model over a folder of images."""

    def __init__(self, model_path: str, device: str = "GPU", img_size: int = 640):
        self.model_path = model_path
        self.device = device
        self.img_size = img_size
        self._compiled = None
        self._input_layer = None
        self._output_layer = None

    def load(self) -> None:
        from openvino.runtime import Core

        core = Core()
        model = core.read_model(str(self.model_path))
        self._compiled = core.compile_model(model, self.device)
        self._input_layer = self._compiled.input(0)
        self._output_layer = self._compiled.output(0)

    def infer_directory(self, images_dir: str, num_images: int = None) -> list[dict]:
        """Classify every .jpg/.png image in ``images_dir``.

        Returns a list of {"source": <filename>, "probabilities": [...]}
        dicts, one per image, in sorted filename order. Unreadable images
        fall back to a uniform distribution rather than aborting the batch.
        """
        import cv2
        import numpy as np

        if self._compiled is None:
            self.load()

        images_path = Path(images_dir).resolve()
        image_files = sorted(
            list(images_path.glob("*.jpg")) + list(images_path.glob("*.png"))
        )
        if not image_files:
            raise RuntimeError(f"No images found in {images_dir}")
        if num_images:
            image_files = image_files[:num_images]

        # Output shape drives class count; infer from a dry compile check
        # by running the first sample and using its vector length thereafter.
        n_classes = None
        results = []

        for img_file in image_files:
            img = cv2.imread(str(img_file))
            if img is None:
                if n_classes is not None:
                    results.append(
                        {"source": img_file.name, "probabilities": [1.0 / n_classes] * n_classes}
                    )
                continue

            img_resized = cv2.resize(img, (self.img_size, self.img_size))
            img_float = img_resized.astype(np.float32) / 255.0
            img_chw = np.transpose(img_float, (2, 0, 1))
            img_batch = np.expand_dims(img_chw, axis=0)

            output = self._compiled([img_batch])[self._output_layer]
            probs = output[0]
            n_classes = len(probs)

            if probs.min() < 0 or probs.sum() < 0.99 or probs.sum() > 1.01:
                exp_probs = np.exp(probs - np.max(probs))
                probs = exp_probs / exp_probs.sum()

            results.append({"source": img_file.name, "probabilities": probs.tolist()})

        return results
