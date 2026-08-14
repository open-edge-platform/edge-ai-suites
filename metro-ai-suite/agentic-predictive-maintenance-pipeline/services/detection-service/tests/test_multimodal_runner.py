# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for multimodal_runner.py — config loading, orchestration, and
persistence, with ImageClassifier/SensorMLPClassifier mocked so tests run
without real model files or datasets.
"""

import json
import os
import tempfile

import pytest

from src.utility.multimodal_runner import (
    MultimodalRunError,
    load_config,
    persist_results,
    run_multimodal_classification,
)


@pytest.fixture
def sample_config():
    return {
        "images_dir": "/data/images",
        "image_model_path": "/models/image/best.xml",
        "sensor_model_path": "/models/sensor/sensor_mlp.xml",
        "sensor_data_path": "/data/sensor.csv",
        "feature_columns": ["MQ2", "MQ3"],
        "join_column": "Corresponding Image Name",
        "class_names": {"0": "Mixture", "1": "NoGas", "2": "Perfume", "3": "Smoke"},
        "fusion_weights": {"image": 0.6, "sensor": 0.4},
    }


def test_load_config_reads_json_file(sample_config):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(sample_config, f)
        path = f.name
    try:
        loaded = load_config(path)
        assert loaded == sample_config
    finally:
        os.unlink(path)


def test_load_config_missing_file_raises():
    with pytest.raises(MultimodalRunError, match="not found"):
        load_config("/nonexistent/path/config.json")


def test_load_config_missing_required_keys_raises(sample_config):
    del sample_config["fusion_weights"]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(sample_config, f)
        path = f.name
    try:
        with pytest.raises(MultimodalRunError, match="fusion_weights"):
            load_config(path)
    finally:
        os.unlink(path)


def test_run_multimodal_classification_fuses_both_branches(sample_config, monkeypatch):
    """Wire fake ImageClassifier/SensorMLPClassifier and confirm the runner
    calls fusion.late_fusion with the branches it produced."""
    import src.utility.multimodal_runner as runner_mod

    class FakeImageClassifier:
        def __init__(self, model_path, device, img_size):
            pass

        def load(self):
            pass

        def infer_directory(self, images_dir):
            return [
                {"source": "img_Smoke.jpg", "probabilities": [0.05, 0.05, 0.05, 0.85]},
                {"source": "img_NoGas.jpg", "probabilities": [0.1, 0.8, 0.05, 0.05]},
            ]

    class FakeSensorClassifier:
        def __init__(self, model_path, data_path, feature_columns, join_column, device):
            pass

        def load(self):
            pass

        def infer(self, sample_keys, n_classes):
            return [
                {"source": key, "probabilities": [0.1, 0.1, 0.1, 0.7],
                 "sensor_raw_json": json.dumps({"MQ2": 1.0})}
                for key in sample_keys
            ]

        @staticmethod
        def sample_key_from_image_name(name):
            return name.rsplit(".", 1)[0]

    monkeypatch.setattr(runner_mod, "ImageClassifier", FakeImageClassifier)
    monkeypatch.setattr(runner_mod, "SensorMLPClassifier", FakeSensorClassifier)

    results = run_multimodal_classification(sample_config, device="CPU")

    assert len(results) == 2
    smoke_result = next(r for r in results if r["source"] == "img_Smoke.jpg")
    assert smoke_result["label"] == "Smoke"
    assert "image_confidence" in smoke_result
    assert "sensor_confidence" in smoke_result
    assert smoke_result["sensor_raw_json"] == json.dumps({"MQ2": 1.0})


def test_run_multimodal_classification_no_images_raises(sample_config, monkeypatch):
    import src.utility.multimodal_runner as runner_mod

    class EmptyImageClassifier:
        def __init__(self, model_path, device, img_size):
            pass

        def load(self):
            pass

        def infer_directory(self, images_dir):
            return []

    monkeypatch.setattr(runner_mod, "ImageClassifier", EmptyImageClassifier)

    with pytest.raises(MultimodalRunError, match="No images found"):
        run_multimodal_classification(sample_config, device="CPU")


def test_persist_results_posts_each_sample_with_no_bounding_box():
    results = [
        {"source": "img_Smoke.jpg", "label": "Smoke", "confidence": 0.9,
         "image_confidence": 0.85, "sensor_confidence": 0.95,
         "sensor_raw_json": "{}"},
        {"source": "img_NoGas.jpg", "label": "NoGas", "confidence": 0.8,
         "image_confidence": 0.75, "sensor_confidence": 0.7,
         "sensor_raw_json": "{}"},
    ]
    posted = []
    inserted = persist_results(results, "gas_detection_multimodal", posted.append)

    assert inserted == 2
    assert len(posted) == 2
    assert posted[0]["frame_id"] == 0
    assert posted[0]["label"] == "Smoke"
    assert posted[0]["x"] == 0.0 and posted[0]["width"] == 0.0
    assert posted[0]["source"] == "gas_detection_multimodal"
    assert posted[1]["frame_id"] == 1


def test_persist_results_continues_after_a_post_failure():
    results = [
        {"source": "a.jpg", "label": "Smoke", "confidence": 0.9},
        {"source": "b.jpg", "label": "NoGas", "confidence": 0.8},
    ]

    def flaky_post(payload):
        if payload["frame_id"] == 0:
            raise ConnectionError("storage-service unreachable")

    inserted = persist_results(results, "gas_detection_multimodal", flaky_post)
    assert inserted == 1
