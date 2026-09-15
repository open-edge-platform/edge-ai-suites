# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for Metrics Manager client integration."""

import os
import sys
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from models import AlertLevel, AlertType, IntersectionData, VLMAlert, VLMAnalysisData
from services.config import MetricsConfig
from services.metrics_client import MetricsManagerClient


@pytest.fixture
def sample_intersection_data():
    return IntersectionData(
        intersection_id="intersection-1",
        intersection_name="Main and First",
        latitude=37.1,
        longitude=-122.1,
        timestamp=datetime.now(timezone.utc),
        north_camera=5,
        south_camera=3,
        east_camera=2,
        west_camera=1,
        total_density=11,
        intersection_status="HIGH",
        north_pedestrian=1,
        south_pedestrian=2,
        east_pedestrian=0,
        west_pedestrian=1,
        total_pedestrian_count=4,
    )


@pytest.fixture
def sample_vlm_analysis():
    return VLMAnalysisData(
        traffic_summary="Heavy northbound traffic.",
        alerts=[
            VLMAlert(
                alert_type=AlertType.CONGESTION,
                level=AlertLevel.WARNING,
                description="Congestion detected.",
            )
        ],
        recommendations=["Adjust signal timing."],
        analysis_timestamp=datetime.now(timezone.utc),
    )


def test_metrics_config_reads_metrics_manager_environment():
    env = {
        "METRICS_MANAGER_URL": "http://metrics-manager:9090/",
        "METRICS_STREAM_URL": "http://metrics-manager:9090/metrics/stream",
        "METRICS_HEALTH_URL": "http://metrics-manager:9090/health",
        "METRICS_PUSH_ENABLED": "false",
        "METRICS_PUSH_TIMEOUT_SECONDS": "0.25",
    }

    with patch.dict(os.environ, env, clear=True):
        config = MetricsConfig()

    assert config.base_url == "http://metrics-manager:9090"
    assert config.stream_url == "http://metrics-manager:9090/metrics/stream"
    assert config.health_url == "http://metrics-manager:9090/health"
    assert config.push_enabled is False
    assert config.push_timeout_seconds == 0.25


def test_build_traffic_metrics_uses_low_cardinality_tags(sample_intersection_data, sample_vlm_analysis):
    with patch.dict(os.environ, {"METRICS_MANAGER_URL": "http://metrics-manager:9090"}, clear=True):
        client = MetricsManagerClient(MetricsConfig())

    metrics = client.build_traffic_metrics(
        sample_intersection_data,
        sample_vlm_analysis,
        active_camera_count=4,
    )

    names = [metric["name"] for metric in metrics]
    assert names.count("stia_traffic") == 1
    assert names.count("stia_vlm_analysis") == 1
    assert names.count("stia_direction_traffic") == 4

    traffic_metric = next(metric for metric in metrics if metric["name"] == "stia_traffic")
    assert traffic_metric["fields"]["total_density"] == 11
    assert traffic_metric["fields"]["total_pedestrian_count"] == 4
    assert traffic_metric["fields"]["active_camera_count"] == 4
    assert traffic_metric["fields"]["intersection_status_code"] == 2
    assert traffic_metric["tags"] == {
        "service": "smart-traffic-intersection-agent",
        "intersection_id": "intersection-1",
        "intersection_name": "Main and First",
    }

    directions = {
        metric["tags"]["direction"]
        for metric in metrics
        if metric["name"] == "stia_direction_traffic"
    }
    assert directions == {"north", "south", "east", "west"}


@pytest.mark.asyncio
async def test_publish_batch_skips_network_when_disabled():
    with patch.dict(os.environ, {"METRICS_PUSH_ENABLED": "false"}, clear=True):
        client = MetricsManagerClient(MetricsConfig())

    with patch("services.metrics_client.aiohttp.ClientSession") as session:
        await client.publish_batch([{"name": "metric", "fields": {"value": 1}, "tags": {}}])

    session.assert_not_called()


@pytest.mark.asyncio
async def test_publish_batch_sends_metrics_when_enabled():
    with patch.dict(
        os.environ,
        {
            "METRICS_MANAGER_URL": "http://metrics-manager:9090",
            "METRICS_PUSH_ENABLED": "true",
            "METRICS_PUSH_TIMEOUT_SECONDS": "1.5",
        },
        clear=True,
    ):
        client = MetricsManagerClient(MetricsConfig())

    posted_payload = {}

    class FakeResponse:
        status = 202

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def text(self):
            return "accepted"

    class FakeSession:
        def __init__(self, *args, **kwargs):
            self.timeout = kwargs.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def post(self, url, json):
            posted_payload["url"] = url
            posted_payload["json"] = json
            return FakeResponse()

    with patch("services.metrics_client.aiohttp.ClientSession", FakeSession):
        await client.publish_batch([{"name": "metric", "fields": {"value": 1}, "tags": {}}])

    assert posted_payload["url"] == "http://metrics-manager:9090/api/v1/metrics"
    assert posted_payload["json"] == {"metrics": [{"name": "metric", "fields": {"value": 1}, "tags": {}}]}


@pytest.mark.asyncio
async def test_publish_batch_handles_rejection_response():
    with patch.dict(
        os.environ,
        {
            "METRICS_MANAGER_URL": "http://metrics-manager:9090",
            "METRICS_PUSH_ENABLED": "true",
        },
        clear=True,
    ):
        client = MetricsManagerClient(MetricsConfig())

    class FakeResponse:
        status = 500

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def text(self):
            return "server error"

    class FakeSession:
        def __init__(self, *args, **kwargs):
            self.timeout = kwargs.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def post(self, url, json):
            return FakeResponse()

    with patch("services.metrics_client.aiohttp.ClientSession", FakeSession):
        await client.publish_batch([{"name": "metric", "fields": {"value": 1}, "tags": {}}])
