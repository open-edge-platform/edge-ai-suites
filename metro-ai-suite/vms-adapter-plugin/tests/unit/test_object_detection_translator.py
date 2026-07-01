# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the DLStreamer → Nx metadata translator."""

from __future__ import annotations

import time
from analytics_app_shim.object_detection.translator import (
    translate_dls_metadata,
    _TYPE_DEFAULT,
    _label_to_type_id,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _sample_payload(*, with_rtp: bool = True, objects: list | None = None) -> dict:
    base: dict = {
        "objects": objects
        if objects is not None
        else [
            {
                "detection": {
                    "bounding_box": {
                        "x_min": 0.10,
                        "y_min": 0.20,
                        "x_max": 0.50,
                        "y_max": 0.60,
                    },
                    "confidence": 0.95,
                    "label": "pedestrian",
                    "label_id": 1,
                },
                "region_id": 42,
                "roi_type": "person",
            }
        ],
    }
    if with_rtp:
        base["rtp"] = {"sender_ntp_unix_timestamp_ns": 1_000_000_000 * 1_000_000}  # 1e15 ns → 1e9 ms
    return base


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_translate_returns_list_and_timestamp():
    objects, ts = translate_dls_metadata(_sample_payload())
    assert isinstance(objects, list)
    assert isinstance(ts, int)
    assert ts > 0


def test_translate_rtp_timestamp_used_when_present():
    # NTP timestamp in payload → used directly (ns → ms).
    ntp_ns = 1_777_350_580_000_000_000
    payload = _sample_payload(with_rtp=False)
    payload["rtp"] = {"sender_ntp_unix_timestamp_ns": ntp_ns}
    _, ts = translate_dls_metadata(payload)
    assert ts == ntp_ns // 1_000_000


def test_translate_wall_clock_used_when_no_rtp():
    before = int(time.time() * 1000)
    _, ts = translate_dls_metadata(_sample_payload(with_rtp=False))
    after = int(time.time() * 1000)
    assert before <= ts <= after


def test_translate_timestamp_offset_applied_to_wall_clock():
    offset = -300
    before = int(time.time() * 1000) + offset
    _, ts = translate_dls_metadata(_sample_payload(with_rtp=False), timestamp_offset_ms=offset)
    after = int(time.time() * 1000) + offset
    assert before <= ts <= after


def test_translate_timestamp_offset_applied_to_ntp():
    ntp_ns = 1_777_350_580_000_000_000
    offset = -500
    payload = _sample_payload(with_rtp=False)
    payload["rtp"] = {"sender_ntp_unix_timestamp_ns": ntp_ns}
    _, ts = translate_dls_metadata(payload, timestamp_offset_ms=offset)
    assert ts == ntp_ns // 1_000_000 + offset


def test_translate_single_object_fields():
    objects, _ = translate_dls_metadata(_sample_payload())
    assert len(objects) == 1
    obj = objects[0]

    assert "trackId" in obj
    assert "typeId" in obj
    assert "boundingBox" in obj
    assert "confidence" in obj
    assert "attributes" in obj

    # bounding box format: "x_min,y_min,widthxheight"
    bbox = obj["boundingBox"]
    parts = bbox.split(",")
    assert len(parts) == 3
    assert "x" in parts[2], "Width×Height part should contain 'x' separator"

    assert abs(obj["confidence"] - 0.95) < 1e-6


def test_translate_bounding_box_values():
    objects, _ = translate_dls_metadata(_sample_payload())
    bbox = objects[0]["boundingBox"]
    x_min_s, y_min_s, wh = bbox.split(",")
    w_s, h_s = wh.split("x")
    assert abs(float(x_min_s) - 0.10) < 1e-3
    assert abs(float(y_min_s) - 0.20) < 1e-3
    assert abs(float(w_s) - 0.40) < 1e-3   # 0.50 - 0.10
    assert abs(float(h_s) - 0.40) < 1e-3   # 0.60 - 0.20


def test_translate_region_id_gives_stable_track_id():
    objects1, _ = translate_dls_metadata(_sample_payload())
    objects2, _ = translate_dls_metadata(_sample_payload())
    assert objects1[0]["trackId"] == objects2[0]["trackId"]


def test_translate_no_region_id_gives_random_track_id():
    payload = _sample_payload()
    payload["objects"][0].pop("region_id")
    objects1, _ = translate_dls_metadata(payload)
    objects2, _ = translate_dls_metadata(payload)
    # Without a region_id, each call generates a new UUID
    assert objects1[0]["trackId"] != objects2[0]["trackId"]


def test_translate_empty_objects_list():
    payload = _sample_payload(objects=[])
    objects, ts = translate_dls_metadata(payload)
    assert objects == []
    assert ts > 0


def test_translate_skips_object_with_missing_bbox():
    bad_obj = {"detection": {"confidence": 0.5, "label": "x"}, "region_id": 1}
    objects, _ = translate_dls_metadata({"objects": [bad_obj]})
    assert objects == []


def test_translate_label_falls_back_to_roi_type():
    obj = {
        "detection": {
            "bounding_box": {"x_min": 0.0, "y_min": 0.0, "x_max": 0.5, "y_max": 0.5},
            "confidence": 0.8,
        },
        "region_id": 7,
        "roi_type": "defect_type_B",
    }
    objects, _ = translate_dls_metadata({"objects": [obj]})
    assert objects[0]["attributes"][0]["value"] == "defect_type_B"


def test_translate_label_falls_back_to_unknown():
    obj = {
        "detection": {
            "bounding_box": {"x_min": 0.0, "y_min": 0.0, "x_max": 0.5, "y_max": 0.5},
            "confidence": 0.8,
        },
        "region_id": 9,
    }
    objects, _ = translate_dls_metadata({"objects": [obj]})
    assert objects[0]["attributes"][0]["value"] == "unknown"


def test_translate_multiple_objects():
    payload = _sample_payload(
        objects=[
            {
                "detection": {
                    "bounding_box": {"x_min": 0.0, "y_min": 0.0, "x_max": 0.1, "y_max": 0.1},
                    "confidence": 0.7,
                    "label": "A",
                },
                "region_id": 1,
            },
            {
                "detection": {
                    "bounding_box": {"x_min": 0.5, "y_min": 0.5, "x_max": 0.9, "y_max": 0.9},
                    "confidence": 0.9,
                    "label": "B",
                },
                "region_id": 2,
            },
        ]
    )
    objects, _ = translate_dls_metadata(payload)
    assert len(objects) == 2
    labels = {o["attributes"][0]["value"] for o in objects}
    assert labels == {"A", "B"}


def _make_obj(label: str) -> dict:
    return {
        "detection": {
            "bounding_box": {"x_min": 0.0, "y_min": 0.0, "x_max": 0.5, "y_max": 0.5},
            "confidence": 0.9,
            "label": label,
        },
        "region_id": 1,
    }


_SAMPLE_MAP = {
    "car": "vap.vehicle",
    "truck": "vap.vehicle",
    "bus": "vap.vehicle",
    "motorcycle": "vap.vehicle",
    "bicycle": "vap.vehicle",
    "van": "vap.vehicle",
    "person": "vap.person",
    "pedestrian": "vap.person",
}


def test_label_to_type_id_hit():
    assert _label_to_type_id("car", _SAMPLE_MAP) == "vap.vehicle"
    assert _label_to_type_id("person", _SAMPLE_MAP) == "vap.person"


def test_label_to_type_id_miss_returns_default():
    assert _label_to_type_id("pallet", _SAMPLE_MAP) == _TYPE_DEFAULT
    assert _label_to_type_id("unknown", {}) == _TYPE_DEFAULT


def test_label_to_type_id_case_insensitive():
    assert _label_to_type_id("Car", _SAMPLE_MAP) == "vap.vehicle"
    assert _label_to_type_id("PERSON", _SAMPLE_MAP) == "vap.person"


def test_type_id_vehicle_labels():
    for label in ("car", "truck", "bus", "motorcycle", "bicycle", "van"):
        objects, _ = translate_dls_metadata({"objects": [_make_obj(label)]}, _SAMPLE_MAP)
        assert objects[0]["typeId"] == "vap.vehicle", f"Expected vap.vehicle for '{label}'"


def test_type_id_person_labels():
    for label in ("person", "pedestrian"):
        objects, _ = translate_dls_metadata({"objects": [_make_obj(label)]}, _SAMPLE_MAP)
        assert objects[0]["typeId"] == "vap.person", f"Expected vap.person for '{label}'"


def test_type_id_unknown_label_falls_back_to_default():
    objects, _ = translate_dls_metadata({"objects": [_make_obj("pallet")]}, _SAMPLE_MAP)
    assert objects[0]["typeId"] == _TYPE_DEFAULT


def test_type_id_no_map_always_default():
    objects, _ = translate_dls_metadata({"objects": [_make_obj("car")]})
    assert objects[0]["typeId"] == _TYPE_DEFAULT


def test_type_id_custom_map():
    custom_map = {"forklift": "custom.forklift", "helmet": "custom.ppe.helmet"}
    objects, _ = translate_dls_metadata({"objects": [_make_obj("forklift")]}, custom_map)
    assert objects[0]["typeId"] == "custom.forklift"
    objects, _ = translate_dls_metadata({"objects": [_make_obj("helmet")]}, custom_map)
    assert objects[0]["typeId"] == "custom.ppe.helmet"
