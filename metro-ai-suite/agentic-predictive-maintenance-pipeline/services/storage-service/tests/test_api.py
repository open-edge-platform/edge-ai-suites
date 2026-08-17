# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import uuid
import pytest
from fastapi.testclient import TestClient

# Point to a test-local db before importing the app.
_db_path = os.path.join(os.path.dirname(__file__), f".api-test-{uuid.uuid4().hex}.db")
os.environ["SQLITE_DB_PATH"] = _db_path

from src.api import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clear_db(client):
    client.delete("/detections")
    yield


# ── Health ────────────────────────────────────────────────────────────────────

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "detections_count" in data


# ── Insert single detection ───────────────────────────────────────────────────

def test_insert_detection(client):
    payload = {
        "frame_id": 1, "label": "Rupture", "confidence": 0.92,
        "x": 100, "y": 200, "width": 50, "height": 40,
    }
    r = client.post("/detections", json=payload)
    assert r.status_code == 201
    assert r.json()["inserted"] == 1


def test_insert_detection_invalid_confidence(client):
    payload = {
        "frame_id": 1, "label": "Deformation", "confidence": 1.5,
        "x": 10, "y": 10, "width": 20, "height": 20,
    }
    r = client.post("/detections", json=payload)
    assert r.status_code == 422


# ── Batch insert ──────────────────────────────────────────────────────────────

def test_insert_batch(client):
    batch = {
        "detections": [
            {"frame_id": 1, "label": "Rupture",    "confidence": 0.9,  "x": 10, "y": 20, "width": 50, "height": 40},
            {"frame_id": 2, "label": "Disconnect", "confidence": 0.85, "x": 30, "y": 40, "width": 60, "height": 50},
            {"frame_id": 3, "label": "Obstacle",   "confidence": 0.6,  "x": 5,  "y": 10, "width": 30, "height": 25},
        ]
    }
    r = client.post("/detections/batch", json=batch)
    assert r.status_code == 201
    assert r.json()["inserted"] == 3


# ── Query detections ──────────────────────────────────────────────────────────

def test_get_all_detections(client):
    _insert_sample(client)
    r = client.get("/detections")
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_filter_by_label(client):
    _insert_sample(client)
    r = client.get("/detections?label=Rupture")
    assert r.status_code == 200
    results = r.json()
    assert all(d["label"] == "Rupture" for d in results)


def test_filter_by_confidence(client):
    _insert_sample(client)
    r = client.get("/detections?min_confidence=0.85")
    assert r.status_code == 200
    results = r.json()
    assert all(d["confidence"] >= 0.85 for d in results)


def test_filter_limit(client):
    _insert_sample(client)
    r = client.get("/detections?limit=1")
    assert r.status_code == 200
    assert len(r.json()) == 1


# ── Structured query ──────────────────────────────────────────────────────────

def test_query_list_contract(client):
    _insert_sample(client)
    r = client.post("/detections/query", json={
        "operation": "list",
        "fields": ["frame_id", "label", "confidence"],
        "filters": [{"field": "confidence", "operator": "gte", "value": 0.6}],
        "sort": [{"field": "confidence", "direction": "desc"}],
        "limit": 2,
        "offset": 0,
    })
    assert r.status_code == 200
    assert r.json() == {
        "data": [
            {"frame_id": 1, "label": "Rupture", "confidence": 0.92},
            {"frame_id": 2, "label": "Disconnect", "confidence": 0.87},
        ],
        "meta": {
            "operation": "list",
            "returned": 2,
            "fields": ["frame_id", "label", "confidence"],
            "limit": 2,
            "offset": 0,
            "has_more": False,
            "grouped_by": [],
        },
    }


@pytest.mark.parametrize("plan, expected", [
    (
        {
            "operation": "count",
            "filters": [{"field": "label", "operator": "eq", "value": "Rupture"}],
        },
        [{"count": 1}],
    ),
    (
        {
            "operation": "aggregate",
            "metrics": [
                {"function": "count", "alias": "detections"},
                {"function": "avg", "field": "confidence", "alias": "avg_confidence"},
            ],
        },
        [{"detections": 3, "avg_confidence": pytest.approx(0.78)}],
    ),
])
def test_query_count_and_aggregate_contract(client, plan, expected):
    _insert_sample(client)
    r = client.post("/detections/query", json=plan)
    assert r.status_code == 200
    assert r.json()["data"] == expected
    assert r.json()["meta"]["operation"] == plan["operation"]


def test_query_group_by_contract(client):
    _insert_sample(client)
    r = client.post("/detections/query", json={
        "operation": "group_by",
        "group_by": ["label"],
        "metrics": [{"function": "count", "alias": "detections"}],
        "sort": [{"field": "detections", "direction": "desc"}],
        "limit": 2,
    })
    assert r.status_code == 200
    data = r.json()
    assert len(data["data"]) == 2
    assert data["meta"]["has_more"] is True
    assert data["meta"]["grouped_by"] == ["label"]


def test_query_frames_contract(client):
    client.post("/detections/batch", json={"detections": [
        {"frame_id": 1, "label": "Rupture", "confidence": 0.9, "x": 1, "y": 2, "width": 3, "height": 4},
        {"frame_id": 1, "label": "Obstacle", "confidence": 0.5, "x": 1, "y": 2, "width": 3, "height": 4},
        {"frame_id": 2, "label": "Rupture", "confidence": 0.8, "x": 1, "y": 2, "width": 3, "height": 4},
    ]})
    r = client.post("/detections/query", json={
        "operation": "frames",
        "sort": [{"field": "detection_count", "direction": "desc"}],
        "limit": 10,
    })
    assert r.status_code == 200
    assert r.json()["data"][0]["frame_id"] == 1
    assert r.json()["data"][0]["detection_count"] == 2


@pytest.mark.parametrize("plan", [
    {"operation": "sql", "sql": "DROP TABLE detections"},
    {"operation": "list", "fields": ["label; DROP TABLE detections"]},
    {"operation": "list", "limit": 501},
    {
        "operation": "list",
        "filters": [{"field": "label", "operator": "eq", "value": ["Rupture"]}],
    },
    {
        "operation": "list",
        "filters": [{"field": "confidence", "operator": "contains", "value": "9"}],
    },
    {
        "operation": "list",
        "filters": [{"field": "frame_id", "operator": "eq", "value": 1.5}],
    },
    {
        "operation": "count",
        "filters": [{"field": "id", "operator": "eq", "value": 999999999999999999999}],
    },
    {
        "operation": "count",
        "filters": [{"field": "x", "operator": "eq", "value": 999999999999999999999}],
    },
    {
        "operation": "aggregate",
        "metrics": [{"function": "avg", "field": "label", "alias": "result"}],
    },
    {
        "operation": "group_by",
        "group_by": ["label"],
        "metrics": [{"function": "count", "alias": "detections"}],
        "sort": [{"field": "not_an_output", "direction": "asc"}],
    },
    {
        "operation": "group_by",
        "group_by": ["label"],
        "metrics": [{"function": "count", "alias": "label"}],
    },
    {"operation": "count", "unexpected": True},
])
def test_query_rejects_unsafe_or_invalid_plans(client, plan):
    r = client.post("/detections/query", json=plan)
    assert r.status_code == 422


def test_query_values_are_parameterized(client):
    _insert_sample(client)
    malicious_value = "Rupture' OR 1=1 --"
    r = client.post("/detections/query", json={
        "operation": "count",
        "filters": [{"field": "label", "operator": "eq", "value": malicious_value}],
    })
    assert r.status_code == 200
    assert r.json()["data"] == [{"count": 0}]
    assert client.get("/detections").status_code == 200


# ── Summary ───────────────────────────────────────────────────────────────────

def test_summary(client):
    _insert_sample(client)
    r = client.get("/detections/summary")
    assert r.status_code == 200
    data = r.json()
    assert "by_class" in data
    assert len(data["by_class"]) > 0
    first = data["by_class"][0]
    assert "label" in first
    assert "count" in first
    assert "avg_confidence" in first


# ── Delete ────────────────────────────────────────────────────────────────────

def test_clear_detections(client):
    _insert_sample(client)
    r = client.delete("/detections")
    assert r.status_code == 204
    r2 = client.get("/detections")
    assert r2.json() == []


# ── Metrics ───────────────────────────────────────────────────────────────────

def test_metrics_endpoint(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "apm_storage_detections_total" in r.text


# ── Helpers ───────────────────────────────────────────────────────────────────

def _insert_sample(client):
    batch = {
        "detections": [
            {"frame_id": 1, "label": "Rupture",    "confidence": 0.92, "x": 10, "y": 20, "width": 50, "height": 40},
            {"frame_id": 2, "label": "Disconnect", "confidence": 0.87, "x": 30, "y": 40, "width": 60, "height": 50},
            {"frame_id": 3, "label": "Obstacle",   "confidence": 0.55, "x": 5,  "y": 10, "width": 30, "height": 25},
        ]
    }
    client.post("/detections/batch", json=batch)
