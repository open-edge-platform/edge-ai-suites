# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import uuid
import pytest

from src.query_models import (
    AggregateMetric,
    AggregateQuery,
    CountQuery,
    FramesQuery,
    GroupByQuery,
    GroupSortSpec,
    ListQuery,
    QueryFilter,
    SortSpec,
)
from src.sqlite_client import SQLiteClient


@pytest.fixture
def db():
    path = os.path.join(os.path.dirname(__file__), f".test-{uuid.uuid4().hex}.db")
    client = SQLiteClient(path)
    yield client
    for suffix in ("", "-shm", "-wal"):
        if os.path.exists(path + suffix):
            os.unlink(path + suffix)


def test_insert_and_query(db):
    db.insert_detection(1, "Rupture", 0.9, 10, 20, 50, 40)
    results = db.get_detections()
    assert len(results) == 1
    assert results[0]["label"] == "Rupture"
    assert results[0]["confidence"] == pytest.approx(0.9)


def test_insert_many(db):
    records = [
        {"frame_id": i, "label": "Deformation", "confidence": 0.5 + i * 0.05,
         "x": i, "y": i, "width": 10, "height": 10}
        for i in range(5)
    ]
    count = db.insert_many(records)
    assert count == 5
    assert db.count() == 5


def test_filter_by_label(db):
    db.insert_detection(1, "Rupture",    0.9,  10, 10, 50, 50)
    db.insert_detection(2, "Disconnect", 0.85, 20, 20, 60, 60)
    results = db.get_detections(label="Rupture")
    assert len(results) == 1
    assert results[0]["label"] == "Rupture"


def test_filter_by_confidence(db):
    db.insert_detection(1, "Rupture", 0.9,  10, 10, 50, 50)
    db.insert_detection(2, "Obstacle", 0.4, 20, 20, 30, 30)
    results = db.get_detections(min_confidence=0.8)
    assert len(results) == 1
    assert results[0]["label"] == "Rupture"


def test_summary(db):
    db.insert_detection(1, "Rupture", 0.9, 10, 10, 50, 50)
    db.insert_detection(2, "Rupture", 0.8, 10, 10, 50, 50)
    db.insert_detection(3, "Obstacle", 0.5, 20, 20, 30, 30)
    summary = db.get_summary()
    by_class = {c["label"]: c for c in summary["by_class"]}
    assert by_class["Rupture"]["count"] == 2
    assert by_class["Obstacle"]["count"] == 1


def test_clear(db):
    db.insert_detection(1, "Rupture", 0.9, 10, 10, 50, 50)
    db.clear()
    assert db.count() == 0


def test_limit(db):
    for i in range(10):
        db.insert_detection(i, "Deformation", 0.6, i, i, 20, 20)
    results = db.get_detections(limit=3)
    assert len(results) == 3


def test_structured_list_query_filters_sorts_and_paginates(db):
    _insert_query_samples(db)
    query = ListQuery(
        operation="list",
        fields=["id", "label", "confidence"],
        filters=[QueryFilter(field="confidence", operator="gte", value=0.6)],
        sort=[SortSpec(field="confidence", direction="desc")],
        limit=2,
    )

    result = db.query_detections(query)

    assert [row["label"] for row in result["data"]] == ["Rupture", "Rupture"]
    assert result["meta"] == {
        "operation": "list",
        "returned": 2,
        "fields": ["id", "label", "confidence"],
        "limit": 2,
        "offset": 0,
        "has_more": True,
        "grouped_by": [],
    }


def test_structured_count_query(db):
    _insert_query_samples(db)
    result = db.query_detections(CountQuery(
        operation="count",
        filters=[QueryFilter(field="label", operator="eq", value="Rupture")],
    ))
    assert result["data"] == [{"count": 3}]
    assert result["meta"]["limit"] is None


def test_structured_aggregate_query(db):
    _insert_query_samples(db)
    result = db.query_detections(AggregateQuery(
        operation="aggregate",
        filters=[QueryFilter(field="label", operator="eq", value="Rupture")],
        metrics=[
            AggregateMetric(function="count", alias="detections"),
            AggregateMetric(function="avg", field="confidence", alias="avg_confidence"),
            AggregateMetric(function="max", field="confidence", alias="max_confidence"),
        ],
    ))
    assert result["data"][0]["detections"] == 3
    assert result["data"][0]["avg_confidence"] == pytest.approx(0.8)
    assert result["data"][0]["max_confidence"] == pytest.approx(0.9)


def test_structured_group_by_query(db):
    _insert_query_samples(db)
    result = db.query_detections(GroupByQuery(
        operation="group_by",
        group_by=["label"],
        metrics=[
            AggregateMetric(function="count", alias="detections"),
            AggregateMetric(function="avg", field="confidence", alias="avg_confidence"),
        ],
        sort=[GroupSortSpec(field="detections", direction="desc")],
        limit=10,
    ))
    assert result["data"][0]["label"] == "Rupture"
    assert result["data"][0]["detections"] == 3
    assert result["meta"]["grouped_by"] == ["label"]


def test_structured_frames_query(db):
    _insert_query_samples(db)
    result = db.query_detections(FramesQuery(
        operation="frames",
        filters=[QueryFilter(field="confidence", operator="gte", value=0.7)],
        limit=10,
    ))
    assert result["data"] == [
        {
            "frame_id": 1,
            "detection_count": 2,
            "avg_confidence": pytest.approx(0.85),
            "min_confidence": pytest.approx(0.8),
            "max_confidence": pytest.approx(0.9),
        },
        {
            "frame_id": 2,
            "detection_count": 1,
            "avg_confidence": pytest.approx(0.7),
            "min_confidence": pytest.approx(0.7),
            "max_confidence": pytest.approx(0.7),
        },
    ]


def test_text_filter_treats_wildcards_as_literals(db):
    db.insert_detection(1, "Rupture", 0.9, 1, 1, 1, 1)
    db.insert_detection(2, "Rup%ture", 0.8, 1, 1, 1, 1)
    query = ListQuery(
        operation="list",
        fields=["label"],
        filters=[QueryFilter(field="label", operator="contains", value="%")],
    )
    assert db.query_detections(query)["data"] == [{"label": "Rup%ture"}]


def _insert_query_samples(db):
    db.insert_many([
        {"frame_id": 1, "label": "Rupture", "confidence": 0.9, "x": 1, "y": 2, "width": 3, "height": 4},
        {"frame_id": 1, "label": "Rupture", "confidence": 0.8, "x": 1, "y": 2, "width": 3, "height": 4},
        {"frame_id": 2, "label": "Rupture", "confidence": 0.7, "x": 1, "y": 2, "width": 3, "height": 4},
        {"frame_id": 3, "label": "Obstacle", "confidence": 0.5, "x": 1, "y": 2, "width": 3, "height": 4},
    ])
