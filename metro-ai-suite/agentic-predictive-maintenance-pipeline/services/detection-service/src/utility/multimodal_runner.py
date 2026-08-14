# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Config-driven orchestration of a fused image + sensor classification run.

Ties together ``ImageClassifier``, ``SensorMLPClassifier``, and
``fusion.late_fusion()`` for a single batch: classify every image in a
directory, classify the paired sensor readings, fuse the two per sample, and
persist each fused result to storage-service. This is the multimodal
counterpart to ``dlstreamer_client.run_pipeline_to_completion`` — same
"batch produces detections" shape, but the source is a static image/sensor
dataset rather than a live DL Streamer video pipeline, so it has no polling
loop.

Use case configs (image/sensor model paths, dataset paths, class names,
fusion weights) are loaded from a JSON file — see
``apps/gas-detection-multimodal/configs/gas_detection.json`` for the
reference config.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from .fusion import late_fusion
from .image_classifier import ImageClassifier
from .sensor_classifier import SensorMLPClassifier

log = logging.getLogger(__name__)


class MultimodalRunError(RuntimeError):
    """Raised when a multimodal classification run cannot complete."""


def load_config(config_path: str) -> dict:
    """Load and lightly validate a multimodal use-case config file."""
    path = Path(config_path)
    if not path.is_file():
        raise MultimodalRunError(f"Multimodal config not found: {config_path}")
    with open(path) as f:
        config = json.load(f)

    required = {"images_dir", "image_model_path", "sensor_model_path",
                "sensor_data_path", "feature_columns", "join_column",
                "class_names", "fusion_weights"}
    missing = required - config.keys()
    if missing:
        raise MultimodalRunError(f"Multimodal config {config_path} missing keys: {sorted(missing)}")
    return config


def run_multimodal_classification(config: dict, device: str = "CPU") -> list[dict]:
    """Classify every image (+ paired sensor row) described by ``config``.

    Returns one fused result dict per sample: ``source`` (image filename),
    ``label``, ``confidence``, ``label_id``, ``probabilities``,
    ``image_confidence``, ``sensor_confidence``, ``sensor_raw_json``.
    """
    class_names = {int(k): v for k, v in config["class_names"].items()}

    image_clf = ImageClassifier(
        model_path=config["image_model_path"],
        device=device,
        img_size=config.get("img_size", 640),
    )
    image_clf.load()
    image_results = image_clf.infer_directory(config["images_dir"])
    if not image_results:
        raise MultimodalRunError(f"No images found under {config['images_dir']}")
    image_probs = {r["source"]: r["probabilities"] for r in image_results}
    sample_ids = list(image_probs.keys())

    sensor_clf = SensorMLPClassifier(
        model_path=config["sensor_model_path"],
        data_path=config["sensor_data_path"],
        feature_columns=config["feature_columns"],
        join_column=config["join_column"],
        device=device,
    )
    sensor_clf.load()
    sensor_keys = [SensorMLPClassifier.sample_key_from_image_name(s) for s in sample_ids]
    sensor_results = sensor_clf.infer(sensor_keys, n_classes=len(class_names))
    sensor_probs = {sample_ids[i]: r["probabilities"] for i, r in enumerate(sensor_results)}
    metadata = {
        sample_ids[i]: {k: v for k, v in r.items() if k == "sensor_raw_json"}
        for i, r in enumerate(sensor_results)
    }

    return late_fusion(
        branch_probs={"image": image_probs, "sensor": sensor_probs},
        fusion_weights=config["fusion_weights"],
        sample_ids=sample_ids,
        class_names=class_names,
        metadata_by_sample=metadata,
    )


def persist_results(results: list[dict], source_tag: str, post_detection_fn) -> int:
    """Persist each fused result via ``post_detection_fn`` (a callable taking
    the same payload shape as ``storage_client.post_detection``).

    Multimodal results have no bounding box, so x/y/width/height are 0.0.
    ``frame_id`` is a per-run incrementing index (0-based), since these
    samples come from a static dataset rather than a video frame sequence.
    """
    inserted = 0
    for frame_id, result in enumerate(results):
        payload = {
            "frame_id": frame_id,
            "label": result["label"],
            "confidence": result["confidence"],
            "x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0,
            "source": source_tag,
            "image_confidence": result.get("image_confidence"),
            "sensor_confidence": result.get("sensor_confidence"),
            "sensor_raw_json": result.get("sensor_raw_json"),
        }
        try:
            post_detection_fn(payload)
            inserted += 1
        except Exception as exc:
            log.warning("Could not persist multimodal result for %s: %s", result.get("source"), exc)
    return inserted
