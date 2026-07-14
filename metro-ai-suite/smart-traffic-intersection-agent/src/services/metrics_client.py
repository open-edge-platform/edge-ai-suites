# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Best-effort Metrics Manager client for STIA application metrics."""

import asyncio
from datetime import datetime, timezone
from typing import Any

import aiohttp
import structlog

from models import IntersectionData, VLMAnalysisData
from .config import MetricsConfig


logger = structlog.get_logger(__name__)


class MetricsManagerClient:
    """Publish low-cardinality STIA metrics to Metrics Manager."""

    _STATUS_CODES = {
        "NORMAL": 0,
        "MODERATE": 1,
        "HIGH": 2,
    }

    def __init__(self, metrics_config: MetricsConfig):
        self.base_url = metrics_config.base_url.rstrip("/")
        self.endpoint = f"{self.base_url}/api/v1/metrics"
        self.enabled = metrics_config.push_enabled
        self.timeout_seconds = metrics_config.push_timeout_seconds

    @staticmethod
    def _timestamp_ns() -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1_000_000_000)

    def build_traffic_metrics(
        self,
        intersection_data: IntersectionData,
        vlm_analysis: VLMAnalysisData,
        active_camera_count: int,
    ) -> list[dict[str, Any]]:
        timestamp = self._timestamp_ns()
        base_tags = {
            "service": "smart-traffic-intersection-agent",
            "intersection_id": intersection_data.intersection_id,
            "intersection_name": intersection_data.intersection_name,
        }

        metrics: list[dict[str, Any]] = [
            {
                "name": "stia_traffic",
                "fields": {
                    "total_density": intersection_data.total_density,
                    "total_pedestrian_count": intersection_data.total_pedestrian_count,
                    "active_camera_count": active_camera_count,
                    "intersection_status_code": self._STATUS_CODES.get(
                        intersection_data.intersection_status,
                        -1,
                    ),
                },
                "tags": base_tags,
                "timestamp": timestamp,
            },
            {
                "name": "stia_vlm_analysis",
                "fields": {
                    "alert_count": len(vlm_analysis.alerts),
                    "recommendation_count": len(vlm_analysis.recommendations or []),
                    "analysis_success": 1,
                },
                "tags": base_tags,
                "timestamp": timestamp,
            },
        ]

        directional_values = {
            "north": (intersection_data.north_camera, intersection_data.north_pedestrian),
            "south": (intersection_data.south_camera, intersection_data.south_pedestrian),
            "east": (intersection_data.east_camera, intersection_data.east_pedestrian),
            "west": (intersection_data.west_camera, intersection_data.west_pedestrian),
        }
        for direction, (vehicle_count, pedestrian_count) in directional_values.items():
            metrics.append(
                {
                    "name": "stia_direction_traffic",
                    "fields": {
                        "vehicle_count": vehicle_count,
                        "pedestrian_count": pedestrian_count,
                    },
                    "tags": {**base_tags, "direction": direction},
                    "timestamp": timestamp,
                }
            )

        return metrics

    async def publish_batch(self, metrics: list[dict[str, Any]]) -> None:
        if not self.enabled or not metrics:
            return

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.endpoint, json={"metrics": metrics}) as response:
                    if response.status >= 400:
                        response_text = await response.text()
                        logger.warning(
                            "Metrics Manager rejected STIA metrics",
                            status=response.status,
                            response=response_text[:300],
                        )
                        return
                    logger.debug(
                        "Published STIA metrics to Metrics Manager",
                        count=len(metrics),
                    )
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.warning("Failed to publish STIA metrics to Metrics Manager", error=str(e))
