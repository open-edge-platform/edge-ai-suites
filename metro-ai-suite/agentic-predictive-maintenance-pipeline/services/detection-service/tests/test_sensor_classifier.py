# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for SensorMLPClassifier CSV loading, normalization, and fallback
behavior, independent of any real OpenVINO model (the compiled model call is
monkeypatched so these tests run without an OpenVINO runtime installed).
"""

import csv
import json

import numpy as np
import pytest

from src.utility.sensor_classifier import SensorMLPClassifier

FEATURE_COLUMNS = ["MQ2", "MQ3", "MQ5", "MQ6", "MQ7", "MQ8", "MQ135"]


@pytest.fixture
def sensor_csv(tmp_path):
    csv_path = tmp_path / "sensors.csv"
    rows = [
        {"Corresponding Image Name": "0_NoGas", "Gas": "NoGas",
         "MQ2": 100, "MQ3": 50, "MQ5": 30, "MQ6": 40, "MQ7": 20, "MQ8": 10, "MQ135": 60},
        {"Corresponding Image Name": "1_Smoke", "Gas": "Smoke",
         "MQ2": 900, "MQ3": 800, "MQ5": 700, "MQ6": 850, "MQ7": 600, "MQ8": 500, "MQ135": 750},
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return csv_path


def test_load_builds_lookup_and_normalization_stats(sensor_csv):
    clf = SensorMLPClassifier(
        model_path="unused.xml",
        data_path=str(sensor_csv),
        feature_columns=FEATURE_COLUMNS,
        join_column="Corresponding Image Name",
    )
    clf.load()

    assert set(clf._lookup.keys()) == {"0_NoGas", "1_Smoke"}
    assert clf._lookup["0_NoGas"] == [100.0, 50.0, 30.0, 40.0, 20.0, 10.0, 60.0]
    # raw readings preserved for auditability
    raw = json.loads(clf._readings_lookup["0_NoGas"]["sensor_raw_json"])
    assert raw["MQ2"] == 100.0
    # std should never be zero (guards div-by-zero for constant columns)
    assert (clf._std > 0).all()


def test_infer_falls_back_to_uniform_for_unknown_sample(sensor_csv):
    clf = SensorMLPClassifier(
        model_path="unused.xml",
        data_path=str(sensor_csv),
        feature_columns=FEATURE_COLUMNS,
        join_column="Corresponding Image Name",
    )
    clf.load()
    clf._ensure_model_loaded = lambda: None  # skip real OpenVINO load
    clf._compiled = object()

    results = clf.infer(["999_Unknown"], n_classes=4)
    assert results == [{"source": "999_Unknown", "probabilities": [0.25, 0.25, 0.25, 0.25]}]


def test_infer_applies_softmax_to_raw_logits(sensor_csv):
    clf = SensorMLPClassifier(
        model_path="unused.xml",
        data_path=str(sensor_csv),
        feature_columns=FEATURE_COLUMNS,
        join_column="Corresponding Image Name",
    )
    clf.load()

    output_layer = object()

    class _FakeCompiled:
        def __call__(self, inputs):
            # Return unnormalized logits to exercise the softmax fallback.
            return {output_layer: np.array([[2.0, 0.0, 0.0, 0.0]], dtype=np.float32)}

    clf._compiled = _FakeCompiled()
    clf._output_layer = output_layer
    clf._ensure_model_loaded = lambda: None

    results = clf.infer(["0_NoGas"], n_classes=4)
    probs = results[0]["probabilities"]
    # softmax([2, 0, 0, 0])
    assert probs == pytest.approx([0.71123451, 0.09625512, 0.09625512, 0.09625512], abs=1e-6)
    assert sum(probs) == pytest.approx(1.0)
    assert "sensor_raw_json" in results[0]


def test_sample_key_from_image_name_strips_extension():
    assert SensorMLPClassifier.sample_key_from_image_name("586_Perfume.png") == "586_Perfume"
