# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Configuration model for the Object Detection (DLStreamer Pipeline Server) analytics app shim."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ObjectDetectionAnalyticsAppConfig(BaseModel):
    """Config for DLStreamer Pipeline Server–based object detection apps (e.g. Loitering Detection)."""

    type: Literal["object_detection"] = "object_detection"
    # Identifies this app instance in API URLs (e.g. "dls_vision" → /v1/analytics-apps/dls_vision/runs)
    app_id: str = "dls_vision"
    display_name: str = "Object Detection"
    base_url: str  # Pipeline Server REST URL
    tls_verify: bool = False
    tls_ca_bundle: str = ""
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    # Broker address as seen by the Pipeline Server (used in the destination payload
    # so gvametapublish can connect). Defaults to the Pipeline Server's MQTT_HOST env var
    # value (container name on the DLStreamer Vision network). Set to "host.docker.internal" if the
    # broker is only reachable via the host's published port.
    pipeline_server_mqtt_host: str = "mqtt-broker"
    pipeline_server_mqtt_port: int = 1883
    # Maps detection labels (case-insensitive) to Nx Witness object typeIds.
    # Any label not present here falls back to "python.detected.object".
    # These typeIds are also merged into the Nx analytics manifest at startup
    # so that Nx accepts pushed objects for all configured types.
    # Example:
    #   label_type_map:
    #     car: vap.vehicle
    #     truck: vap.vehicle
    #     person: vap.person
    #     forklift: custom.forklift
    label_type_map: dict[str, str] = Field(default_factory=dict)
    # Compensates for the delay between frame capture and MQTT message arrival
    # (inference latency + pipeline overhead). A negative value shifts the pushed
    # metadata timestamp backward so it aligns with the corresponding video frame
    # in Nx. For example, -300 corrects for ~300 ms of inference latency.
    # Has no effect when sender_ntp_unix_timestamp_ns is present in the payload.
    metadata_timestamp_offset_ms: int = 0
